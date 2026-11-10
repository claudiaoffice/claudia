// Opening a document: which app it belongs to decides which session shows it, and only the server knows.
import { BaseSession, type SessionOptions } from './base-session'
import type { LinkLike } from './protocol'
import { Session } from './session'
import { SlideSession } from './slide-session'
import { TextSession } from './text-session'

export type AnySession = Session | TextSession | SlideSession

/** What `/api/docs` answers: the app this server serves, and the documents it holds. */
export interface ServerListing {
  app?: string
  documents?: { app?: string }[]
}

/** One document as `/api/docs` lists it. */
export interface Listed {
  id: string
  app: string
  modified: string
  online: number
}

export interface DocsListing {
  app: string
  documents: Listed[]
}

/**
 * Ask a server's `/api/docs` for its document list, for the Open dialog (UX-12).
 *
 * Boiled down to two shapes on purpose: either the listing, or a message fit to show in place of it
 * (`OpenDialog.vue`'s `listError`) — never anything the page would have to guess the meaning of. The bug this
 * replaces treated every answer but a 404 as success and assigned `said.documents` straight into a `ref<Listed[]>`:
 * fine while a server had nothing to say but "here are your documents", but a server that refuses the request
 * (401, needing its access secret; 403; a proxy's own error page) answers with something that has no `documents`
 * array, and the dialog crashed reading `.length` off `undefined` — the whole page went blank, not just the one
 * document a person was looking for.
 */
export async function fetchDocsListing(origin: string, fetchImpl: typeof fetch = fetch): Promise<DocsListing | { error: string }> {
  let response: Response
  try {
    response = await fetchImpl(`${origin}/api/docs`)
  } catch {
    return { error: 'The server cannot be reached.' }
  }
  if (response.status === 404) return { error: 'This server does not list its documents. Type the name of yours.' }
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    /* an empty or non-JSON body: `body` stays null, which becomes a generic error below either way */
  }
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail
    return { error: typeof detail === 'string' ? detail : `The server answered with an error (${response.status}).` }
  }
  const said = body as ServerListing | null
  if (!said || !Array.isArray(said.documents)) return { error: 'The server did not answer with a document list.' }
  return { app: said.app ?? '', documents: said.documents as Listed[] }
}

/**
 * Which app a server serves, for the page that greets somebody before any document is open.
 *
 * The server says so itself and always has. Reading it only off the first listed document — as this page did —
 * means an empty server looks like whatever the fallback is, which is how three servers started side by side all
 * greeted their visitors as computes. The document stays as a second source for an older server that does not say.
 */
export function appOfServer(said: ServerListing | null | undefined): string {
  return said?.app || said?.documents?.[0]?.app || 'claudia'
}

/** Connect, and give back the session of the document's app, loaded and open. A refused handshake is thrown. */
export async function openSession(makeLink: () => LinkLike, options: SessionOptions = {}): Promise<AnySession> {
  const probe = makeLink()
  const welcome = await probe.connect()
  probe.close()
  const session: AnySession =
    welcome.app === 'composes'
      ? new TextSession(makeLink, options)
      : welcome.app === 'creates'
        ? new SlideSession(makeLink, options)
        : new Session(makeLink, options)
  session.justCreated = welcome.created === true
  try {
    await session.open()
  } catch (error) {
    session.close()
    throw error
  }
  return session
}

export const isText = (session: BaseSession<any>): session is TextSession => session instanceof TextSession
export const isSlides = (session: BaseSession<any>): session is SlideSession => session instanceof SlideSession
