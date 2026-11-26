// Opening a document: which app it belongs to decides which session shows it, and only the server knows.
import type { SessionOptions } from './base-session'
import type { LinkLike } from './protocol'
import { parseNotes, type Span } from './notes-markdown'
import { ProtocolError } from './protocol'
import { Session } from './session'
import { SlideSession } from './slide-session'
import { TextSession } from './text-session'

import { languageNow, translate as t } from './i18n'
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
  /** What the owner said the document is about (Markdown), plain in the file: anybody who can list can read it. An
   *  older server says nothing. */
  description?: string
  tags?: string[]
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

/** Connect, and give back the session of the document's app, loaded and open. A refused handshake is thrown.
 * `onAnswered` is called once the server has answered, before the document is loaded. */
export async function openSession(makeLink: () => LinkLike, options: SessionOptions = {}, onAnswered?: () => void): Promise<AnySession> {
  const probe = makeLink()
  const welcome = await probe.connect()
  probe.close()
  onAnswered?.() // the server has made or found the document (an imported file has been read): now it is loaded
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

/** The documents whose id, tags or description hold every word of `query` (case and accents ignored), of `app` if one
 *  is given. The contents are sealed, so what the manifest says in the open is all there is to search (D431, D103). */
export function filterListed<T extends { id: string; app: string; description?: string; tags?: string[] }>(
  documents: T[],
  query: string,
  app = '',
): T[] {
  const words = fold(query).split(/\s+/).filter(Boolean)
  return documents.filter((d) => {
    if (app && d.app !== app) return false
    const text = fold([d.id, d.description ?? '', ...(d.tags ?? [])].join('\n'))
    return words.every((w) => text.includes(w))
  })
}

/** The documents that carry `tag` (all of them for an empty one). */
export function filterByTag<T extends { tags?: string[] }>(documents: T[], tag: string): T[] {
  const wanted = tag.trim().toLowerCase()
  return wanted ? documents.filter((d) => d.tags?.includes(wanted)) : documents
}

/** Every tag used on a place and in how many documents: the most used first, then alphabetically. */
export function tagCounts(documents: { tags?: string[] }[]): { tag: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const d of documents) for (const tag of d.tags ?? []) counts.set(tag, (counts.get(tag) ?? 0) + 1)
  return [...counts].map(([tag, count]) => ({ tag, count })).sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag))
}

/** The tags a person typed, as the server keeps them: split at commas, trimmed, lower case, no empty one, no repeat. */
export function tagsFromText(text: string): string[] {
  const seen = new Set<string>()
  for (const part of text.split(',')) {
    const tag = part.trim().replace(/\s+/g, ' ').toLowerCase()
    if (tag) seen.add(tag)
  }
  return [...seen]
}

/** Most tags a document has, and most characters of one: what the server keeps (`claudia_document_file.MAX_TAGS`, `MAX_TAG`). */
export const MAX_TAGS = 10
export const MAX_TAG = 30
export const MAX_DESCRIPTION = 2000

/** `typed` added to `tags`: all of its tags at once (it may hold several, split by commas), none twice, at most ten, none
 *  longer than thirty characters. What was left out is said in `problem`, a sentence for the person ('' if nothing). */
export function addTags(tags: string[], typed: string): { tags: string[]; problem: string } {
  const result = [...tags]
  let problem = ''
  for (const tag of tagsFromText(typed)) {
    if (result.includes(tag)) continue
    if (result.length >= MAX_TAGS) {
      problem = t('A document has at most {count} tags.', { count: MAX_TAGS })
      break
    }
    if (tag.length > MAX_TAG) {
      problem = t('A tag has at most {count} characters.', { count: MAX_TAG })
      continue
    }
    result.push(tag)
  }
  return { tags: result, problem }
}

/** The tags of the place to suggest for what is being typed: those that start with it and are not taken yet. */
export function tagChoices(counts: { tag: string; count: number }[], typed: string, taken: string[]) {
  const start = fold(typed.trim())
  return counts.filter((c) => !taken.includes(c.tag) && fold(c.tag).startsWith(start))
}

/** The one line a list shows of a description: its first line, with the inline Markdown read as looks. It is never
 *  HTML (the same small reader as the speaker notes, D347): nothing in it can put markup, a picture or a script on
 *  anybody's screen, and a link shows its words but is not something to click in a list. */
export function summaryOf(description: string | undefined): Span[] {
  const first = parseNotes(description ?? '').find((line) => !line.blank)
  return first ? first.spans : []
}

/** Change the description and tags of a document without opening it: connect as its owner (the link is made with the
 *  owner's name and password), ask, and let go. Gives what the server kept, or a sentence for the person. */
export function saveDetails(
  makeLink: () => LinkLike,
  password: string,
  description: string,
  tags: string[],
): Promise<{ description: string; tags: string[] } | { error: string }> {
  return askOnce(makeLink, 'set_details', { password, description, tags })
}

/** Delete a document from the server for good, from the front page (D1608): an owner's own password confirms it. */
export function deleteFromServer(makeLink: () => LinkLike, password: string): Promise<{ deleted: true } | { error: string }> {
  return askOnce(makeLink, 'delete_document', { password })
}

/** One request to a document that is not open: connect as the person, ask, close. A refusal is the server's sentence. */
async function askOnce<T>(makeLink: () => LinkLike, method: string, params: Record<string, unknown>): Promise<T | { error: string }> {
  const link = makeLink()
  try {
    await link.connect()
    return await link.request<T>(method, params)
  } catch (error) {
    if (error instanceof ProtocolError) return { error: error.message }
    return { error: t('The server cannot be reached.') }
  } finally {
    link.close()
  }
}

function fold(text: string): string {
  return text.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

/** What `POST /api/uploads` said about a file (D440). */
export interface Uploaded {
  upload: string
  name: string
  /** `docx`, `odt`, `xlsx`, `ods`, `pptx`, `odp`, `claudia` or `claudia-export` (an unencrypted export, D1272) */
  format: string
  app: string
  size: number
  /** Does this server host the file's app? */
  hosted: boolean
  /** An Office or OpenDocument file: an id made from its name, and its kind in words. */
  suggested_id?: string
  kind?: string
  /** A Claudia file: its own name (`id` on the wire), whether this server holds a document of that name already,
   *  and the name of the document here that is the very same one (what the file is made of, not its name, decides:
   *  it may be called otherwise here), else null. The file's random id is never sent. */
  id?: string
  exists?: boolean
  same_document?: string | null
  /** What the file says about itself (properties of an office file, the manifest of a Claudia one) to offer as a
   *  start: the person may keep, change or clear it. */
  description?: string
  tags?: string[]
  /** A Claudia export: who made it and when, as the file says (D1272), and whether it brings the history of the
   *  original (D2005). */
  made_by?: string
  made_at?: string
  with_history?: boolean
}

/** The file types the file picker offers: every one Claudia opens (sheet 10, B2). */
export const OPENABLE = '.claudia,.docx,.odt,.xlsx,.ods,.pptx,.odp,.zip'

/** The Office and OpenDocument formats of each app (the server's `formats.sniff` decides by the bytes; this is only
 * the name, for the picker and for refusing early). */
const FORMATS: Record<string, readonly string[]> = {
  composes: ['.docx', '.odt'],
  computes: ['.xlsx', '.ods'],
  creates: ['.pptx', '.odp'],
}

/** What the shell's native menu asks of the start page (sheet 11): the entries the manifest keeps there (`start`). */
export type StartPageAction =
  | { kind: 'choose-file' }
  | { kind: 'find-document' }
  | { kind: 'new-document' }
  | { kind: 'dark'; on: boolean | undefined }
  | { kind: 'language'; tag: string }
  | { kind: 'about' }

/** The start page's own action for a menu entry of the shell, or `null` for one it has nothing to do for. About is on
 * the list because the Windows and macOS clients have no About dialog of their own (CODE-94). */
export function startPageAction(action: string, target?: string): StartPageAction | null {
  if (action === 'file.open-file') return { kind: 'choose-file' }
  if (action === 'file.open') return { kind: 'find-document' }
  if (action === 'file.new') return { kind: 'new-document' }
  if (action === 'help.about') return { kind: 'about' }
  if (action === 'view.dark') return { kind: 'dark', on: target === undefined ? undefined : target === 'on' }
  if (action.startsWith('config.language.')) return { kind: 'language', tag: action.slice('config.language.'.length) }
  return null
}

/** What the file picker offers: everything in a browser tab, only the window's own app in a desktop window (D444). */
export function openableFor(windowApp: string | null): string {
  const own = windowApp ? FORMATS[windowApp] : undefined
  return own ? [...own, '.claudia', '.zip'].join(',') : OPENABLE
}

/** The app an Office or OpenDocument file belongs to, by its name; `null` for a Claudia file (which app it is, only
 * its contents say) and anything else. */
export function appOfFileName(name: string): string | null {
  const dot = name.lastIndexOf('.')
  const extension = dot < 0 ? '' : name.slice(dot).toLowerCase()
  return Object.entries(FORMATS).find(([, formats]) => formats.includes(extension))?.[0] ?? null
}

/** A file on its way to the server: `done` is the answer, a message fit to show, or `{ cancelled }` after `abort`. */
export interface Upload {
  done: Promise<Uploaded | { error: string } | { cancelled: true }>
  abort: () => void
}

/** Hand a file to the server (D440), telling `onProgress` how much of it is there (0 to 1) as it goes: a large file
 * takes a while, and `fetch` cannot tell how far an upload is, so this is an `XMLHttpRequest`. */
export function sendFile(
  origin: string,
  file: Blob & { name: string },
  onProgress: (fraction: number) => void,
  makeXhr: () => XMLHttpRequest = () => new XMLHttpRequest(),
): Upload {
  const xhr = makeXhr()
  const done = new Promise<Uploaded | { error: string } | { cancelled: true }>((resolve) => {
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total)
    }
    xhr.onload = () => resolve(answerOf(xhr.status, xhr.responseText))
    xhr.onerror = () => resolve({ error: t('The server cannot be reached.') })
    xhr.onabort = () => resolve({ cancelled: true })
  })
  xhr.open('POST', `${origin}/api/uploads`)
  xhr.setRequestHeader('accept-language', languageNow()) // a refusal comes back in the page's language (D2003)
  xhr.setRequestHeader('content-type', 'application/octet-stream')
  xhr.setRequestHeader('x-claudia-name', encodeURIComponent(file.name))
  xhr.send(file)
  return { done, abort: () => xhr.abort() }
}

function answerOf(status: number, text: string): Uploaded | { error: string } {
  if (status === 413) return { error: t('The file is too large for this server.') }
  if (status === 415) return { error: t('This is not a file Claudia can open.') }
  let body: unknown = null
  try {
    body = JSON.parse(text)
  } catch {
    /* no JSON: the status says enough */
  }
  if (status >= 200 && status < 300 && body) return body as Uploaded
  const said = (body as { detail?: unknown } | null)?.detail
  return { error: typeof said === 'string' ? said : t('The server answered with an error ({status}).', { status }) }
}

/** Put an uploaded Claudia file into this server as it is (D442). */
export async function placeUpload(origin: string, token: string, fetchImpl: typeof fetch = fetch): Promise<{ app: string; id: string } | { error: string }> {
  let response: Response
  try {
    response = await fetchImpl(`${origin}/api/uploads/${encodeURIComponent(token)}/place`, {
      method: 'POST',
      headers: { 'accept-language': languageNow() },
    })
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
