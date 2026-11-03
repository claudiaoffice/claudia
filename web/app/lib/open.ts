// Opening a document: which app it belongs to decides which session shows it, and only the server knows.
import { BaseSession, type SessionOptions } from './base-session'
import type { LinkLike } from './protocol'
import { Session } from './session'
import { TextSession } from './text-session'

export type AnySession = Session | TextSession

/** Connect, and give back the session of the document's app, loaded and open. A refused handshake is thrown. */
export async function openSession(makeLink: () => LinkLike, options: SessionOptions = {}): Promise<AnySession> {
  const probe = makeLink()
  const welcome = await probe.connect()
  probe.close()
  const session: AnySession = welcome.app === 'composes' ? new TextSession(makeLink, options) : new Session(makeLink, options)
  try {
    await session.open()
  } catch (error) {
    session.close()
    throw error
  }
  return session
}

export const isText = (session: BaseSession<any>): session is TextSession => session instanceof TextSession
