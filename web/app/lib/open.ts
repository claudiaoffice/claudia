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
