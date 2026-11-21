// The wire protocol of a claudia server: JSON frames over one WebSocket per person and document.
//   -> {id, method, params}     <- {id, ok, result | error}     <- {event, data} (pushed)
// The first frame is `hello` with the name and password; the answer carries the welcome data.

import { translate as t } from './i18n'

export class ProtocolError extends Error {
  constructor(
    public code: string,
    message: string,
    /** For `too_many_tries`: the seconds the server asks the person to wait (D1266). */
    public retryAfter?: number,
  ) {
    super(message)
  }
}

export interface SocketLike {
  send(data: string): void
  close(code?: number): void
  onopen: (() => void) | null
  onmessage: ((event: { data: unknown }) => void) | null
  onclose: ((event: { code: number }) => void) | null
}

export interface Welcome {
  user: string
  role: 'owner' | 'editor' | 'viewer'
  doc: string
  app: string
  branch: string
  revision: string | null
  id: number
  color: string
  /** The locale the server negotiated for this connection (E5.7, D31): what was sent, or 'en' if nothing was, or
   *  what was sent could not be read as a locale tag. The server says its own messages and help in it (D322, D323). */
  locale: string
  people: { id: number; user: string; color: string }[]
  presence: { user: string; regions: Region[]; locked: boolean }[]
  checkpoints: { number: number; label: string; author: string | null }[]
  limits: { max_text: number }
  /** True if this very hello made the document (so its owner should now be given a recovery key). */
  created?: boolean
  /** The file this document was just made from (D438, D439): its name, format, whether it is kept inside, and what
   *  the document does not show, as loss codes. Only in the welcome of the hello that imported it. */
  imported?: { name: string; format: string; kept: boolean; losses: { kind: string; detail: string; count: number }[] }
  /** Every branch of the document's history: the active one and the ones a restore left behind (E3.8). */
  branches: BranchInfo[]
  /** A restore/switch suggestion waiting for everybody's answer, if one is open right now (E3.7). */
  proposal: RestoreProposal | null
  /** One-time notice of what happened, while this person was away, to the branch they were on (E3.7). */
  returned: RestoreResolution | null
}

/** One branch of a document's history, as `branches` and a `Welcome` carry it. */
export interface BranchInfo {
  name: string
  head: string | null
  active: boolean
  forked_from: string | null
}

/** A suggestion to restore a checkpoint or switch the branch, open and waiting for answers (E3.7). */
export interface RestoreProposal {
  id: number
  kind: 'restore' | 'switch'
  by: string
  checkpoint: number | null
  branch: string | null
  label: string
  opened_at: number
  expires_at: number
  policy: 'consensus' | 'veto'
  group: string[]
  agreed: string[]
}

/** What became of a branch that stopped being active while somebody was away (the `Welcome.returned` notice). */
export interface RestoreResolution {
  by: string
  kind: 'restore' | 'switch'
  label: string
  agreed: string[]
}

export interface CellRef {
  row: number
  col: number
  sheet?: string | null
}
export interface CellsRegion {
  kind: 'cells'
  range: { first: CellRef; last: CellRef }
}
/** A stretch of one paragraph; an empty one is a caret. Offsets count characters (code points) as the server does. */
export interface TextRegion {
  kind: 'text'
  block: string
  start: number
  end: number
}
/** The floating objects of a slide (creates) or a sheet (computes) that somebody has selected (and so holds).
 * Exactly one of `slide`/`sheet` is set, matching the app the region came from (each app sends only its own
 * shape, never both). */
export interface ObjectsRegion {
  kind: 'objects'
  /** The slide, sheet or paragraph the objects are on: one field in all three apps (E10.16, D177). */
  container: string
  ids: string[]
}
export type Region = CellsRegion | TextRegion | ObjectsRegion

/** A value as it came off the wire (parsed JSON), before the code that knows its event or method reads it.
 *  Deliberately `any`, and the one place it is written: each reader knows the shape its event or method sends, and
 *  `unknown` would only move the same cast into every one of them. Anything else typed `any` is a lint error. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type WireData = any

export type EventHandler = (name: string, data: WireData) => void
export type CloseHandler = (code: number, requested: boolean) => void

export interface LinkOptions {
  url: string
  user: string
  password: string
  create?: boolean
  /** Come in with the recovery key instead of the password: `password` is then the *new* one. */
  recoveryKey?: string
  /** Make the new document from this upload (`POST /api/uploads`, D440); with `create`. */
  upload?: string
  /** With `upload`: keep the file inside the document (the default) for an exact round trip (D439). */
  keepOriginal?: boolean
  /** With `upload`: what the document is about (Markdown) and its tags: kept plain in the file, so anybody who can list
   *  the server can read them. */
  description?: string
  tags?: string[]
  /** The client's own locale (E5.7, D31) — always a client setting, never stored on the server. Omitted, it is not
   *  sent and the server assumes 'en'. */
  locale?: string
  socket?: (url: string) => SocketLike
}

/** The things a session needs from a connection (a fake one stands in for it in tests). */
export interface LinkLike {
  connect(): Promise<Welcome>
  request<T = WireData>(method: string, params?: Record<string, unknown>): Promise<T>
  onEvent(handler: EventHandler): void
  onClose(handler: CloseHandler): void
  close(): void
}

export class Link implements LinkLike {
  private socket: SocketLike | null = null
  private nextId = 1
  private pending = new Map<number, { resolve: (value: WireData) => void; reject: (error: ProtocolError) => void }>()
  private eventHandlers: EventHandler[] = []
  private closeHandlers: CloseHandler[] = []
  private requestedClose = false
  private closed = false

  constructor(private options: LinkOptions) {}

  onEvent(handler: EventHandler) {
    this.eventHandlers.push(handler)
  }

  onClose(handler: CloseHandler) {
    this.closeHandlers.push(handler)
  }

  connect(): Promise<Welcome> {
    const { url, user, password, create = false, recoveryKey, locale, upload, keepOriginal, description, tags } = this.options
    const make = this.options.socket ?? ((u: string) => new WebSocket(u) as unknown as SocketLike)
    const socket = (this.socket = make(url))
    return new Promise<Welcome>((resolve, reject) => {
      socket.onopen = () => {
        const id = this.nextId++
        this.pending.set(id, { resolve, reject })
        const params: Record<string, unknown> =
          recoveryKey === undefined ? { user, password, create } : { user, password, recovery_key: recoveryKey }
        if (locale !== undefined) params.locale = locale
        if (upload !== undefined && create) {
          params.upload = upload
          params.keep_original = keepOriginal !== false
          if (description) params.description = description
          if (tags?.length) params.tags = tags
        }
        socket.send(JSON.stringify({ id, method: 'hello', params }))
      }
      socket.onmessage = (event) => this.receive(String(event.data))
      socket.onclose = (event) => {
        this.closed = true
        const error = new ProtocolError('closed', t('the connection closed ({code})', { code: event.code }))
        reject(error) // no effect once the welcome has come; before it, nobody is left waiting for ever
        for (const waiting of this.pending.values()) waiting.reject(error)
        this.pending.clear()
        for (const handler of this.closeHandlers) handler(event.code, this.requestedClose)
      }
    })
  }

  request<T = WireData>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (!this.socket || this.closed) return Promise.reject(new ProtocolError('closed', t('not connected')))
    const id = this.nextId++
    const sent = new Promise<T>((resolve, reject) => this.pending.set(id, { resolve, reject }))
    this.socket.send(JSON.stringify({ id, method, params }))
    return sent
  }

  close() {
    this.requestedClose = true
    this.socket?.close(1000)
  }

  private receive(text: string) {
    let frame: WireData
    try {
      frame = JSON.parse(text)
    } catch {
      return
    }
    if (typeof frame.event === 'string') {
      for (const handler of this.eventHandlers) handler(frame.event, frame.data)
      return
    }
    const waiting = this.pending.get(frame.id)
    if (!waiting) return
    this.pending.delete(frame.id)
    if (frame.ok) waiting.resolve(frame.result)
    else waiting.reject(new ProtocolError(frame.error?.code ?? 'internal', frame.error?.message ?? t('request failed'), frame.error?.retry_after))
  }
}

/** `ws(s)://host/api/<app>/docs/<id>/ws` for the page's own server (or for the server named by `?server=` in dev).
 *  Without `app`, the address without one (D431): the server opens the first app that has the document. */
export function socketUrl(doc: string, page: { protocol: string; host: string }, app?: string): string {
  const scheme = page.protocol === 'https:' ? 'wss' : 'ws'
  const where = app ? `/api/${encodeURIComponent(app)}/docs/` : '/api/docs/'
  return `${scheme}://${page.host}${where}${encodeURIComponent(doc)}/ws`
}

/** What a close code of the handshake means for the person. */
export function closeMessage(code: number): string {
  switch (code) {
    case 4400:
      return t('The server did not understand the request.')
    case 4401:
      return t('The name or password is not right.')
    case 4403:
      return t('This page is not allowed to use that server.')
    case 4404:
      return t('There is no such document.')
    case 4408:
      return t('The server did not hear from the page in time.')
    case 4429:
      return t('Too many tries. Try again in a little while.')
    case 4423:
      return t('An editor or owner has to open this document first. This window will open it as soon as one has.')
    case 1013:
      return t('The document is full, or the connection was too slow.')
    default:
      return t('The connection to the server was lost.')
  }
}
