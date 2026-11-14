// Opening a document: which app it belongs to decides which session shows it, and only the server knows.
import type { SessionOptions } from './base-session'
import type { LinkLike } from './protocol'
import { Session } from './session'
import { SlideSession } from './slide-session'
import { TextSession } from './text-session'

import { translate as t } from './i18n'
export type AnySession = Session | TextSession | SlideSession

/** What `/api/docs` answers: the app this server serves (`null` on a server of several, D430), the apps it hosts,
 *  and the documents of all of them. */
export interface ServerListing {
  app?: string | null
  apps?: string[]
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
  /** The apps the server hosts, in its order; an older server that does not say hosts the one `app`. */
  apps: string[]
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
    return { error: t('The server cannot be reached.') }
  }
  if (response.status === 404) return { error: t('This server does not list its documents. Type the name of yours.') }
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    /* an empty or non-JSON body: `body` stays null, which becomes a generic error below either way */
  }
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail
    return { error: typeof detail === 'string' ? detail : t('The server answered with an error ({status}).', { status: response.status }) }
  }
  const said = body as ServerListing | null
  if (!said || !Array.isArray(said.documents)) return { error: t('The server did not answer with a document list.') }
  const apps = Array.isArray(said.apps) ? said.apps.filter((a): a is string => typeof a === 'string') : said.app ? [said.app] : []
  return { app: said.app ?? '', apps, documents: said.documents as Listed[] }
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
  session.imported = welcome.imported ?? null
  try {
    await session.open()
  } catch (error) {
    session.close()
    throw error
  }
  return session
}

export const isText = (session: AnySession): session is TextSession => session instanceof TextSession
export const isSlides = (session: AnySession): session is SlideSession => session instanceof SlideSession

/** The documents whose id holds every word of `query` (case and accents ignored), of `app` if one is given. The
 *  contents are sealed, so the id is all there is to search (D431). */
export function filterListed<T extends { id: string; app: string }>(documents: T[], query: string, app = ''): T[] {
  const words = fold(query).split(/\s+/).filter(Boolean)
  return documents.filter((d) => (!app || d.app === app) && words.every((w) => fold(d.id).includes(w)))
}

function fold(text: string): string {
  return text.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

/** What `POST /api/uploads` said about a file (D440). */
export interface Uploaded {
  upload: string
  name: string
  /** `docx`, `odt`, `xlsx`, `ods`, `pptx`, `odp` or `claudia` */
  format: string
  app: string
  size: number
  /** Does this server host the file's app? */
  hosted: boolean
  /** An Office or OpenDocument file: an id made from its name, and its kind in words. */
  suggested_id?: string
  kind?: string
  /** A Claudia file: its own id and title, and whether this server holds a document of that id already. */
  id?: string
  title?: string
  exists?: boolean
}

/** The file types the file picker offers: every one Claudia opens (sheet 10, B2). */
export const OPENABLE = '.claudia,.docx,.odt,.xlsx,.ods,.pptx,.odp'

/** Hand a file to the server (D440). The answer, or a message fit to show. */
export async function uploadFile(origin: string, file: Blob & { name: string }, fetchImpl: typeof fetch = fetch): Promise<Uploaded | { error: string }> {
  let response: Response
  try {
    response = await fetchImpl(`${origin}/api/uploads`, {
      method: 'POST',
      headers: { 'content-type': 'application/octet-stream', 'x-claudia-name': encodeURIComponent(file.name) },
      body: file,
    })
  } catch {
    return { error: t('The server cannot be reached.') }
  }
  if (response.status === 413) return { error: t('The file is too large for this server.') }
  if (response.status === 415) return { error: t('This is not a file Claudia can open.') }
  if (!response.ok) return { error: await detail(response) }
  return (await response.json()) as Uploaded
}

/** Put an uploaded Claudia file into this server as it is (D442). */
export async function placeUpload(origin: string, token: string, fetchImpl: typeof fetch = fetch): Promise<{ app: string; id: string } | { error: string }> {
  let response: Response
  try {
    response = await fetchImpl(`${origin}/api/uploads/${encodeURIComponent(token)}/place`, { method: 'POST' })
  } catch {
    return { error: t('The server cannot be reached.') }
  }
  if (!response.ok) return { error: await detail(response) }
  return (await response.json()) as { app: string; id: string }
}

async function detail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
  } catch {
    /* no JSON: the status says enough */
  }
  return t('The server answered with an error ({status}).', { status: response.status })
}
