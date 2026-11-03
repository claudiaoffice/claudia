// The wire protocol of a claudia server: JSON frames over one WebSocket per person and document.
//   -> {id, method, params}     <- {id, ok, result | error}     <- {event, data} (pushed)
// The first frame is `hello` with the name and password; the answer carries the welcome data.

export class ProtocolError extends Error {
  constructor(
    public code: string,
    message: string,
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
  line: string
  revision: string | null
  id: number
  color: string
  people: { id: number; user: string; color: string }[]
  presence: { user: string; regions: Region[]; locked: boolean }[]
  checkpoints: { number: number; label: string; author: string | null }[]
  limits: { max_text: number }
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
/** The objects of a slide that somebody has selected (and so holds). */
export interface ObjectsRegion {
  kind: 'objects'
  slide: string
  ids: string[]
}
export type Region = CellsRegion | TextRegion | ObjectsRegion

export type EventHandler = (name: string, data: any) => void
export type CloseHandler = (code: number, requested: boolean) => void

export interface LinkOptions {
  url: string
  user: string
  password: string
  create?: boolean
  socket?: (url: string) => SocketLike
}

/** The things a session needs from a connection (a fake one stands in for it in tests). */
export interface LinkLike {
  connect(): Promise<Welcome>
  request<T = any>(method: string, params?: Record<string, unknown>): Promise<T>
  onEvent(handler: EventHandler): void
  onClose(handler: CloseHandler): void
  close(): void
}

export class Link implements LinkLike {
  private socket: SocketLike | null = null
  private nextId = 1
  private pending = new Map<number, { resolve: (value: any) => void; reject: (error: ProtocolError) => void }>()
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
    const { url, user, password, create = false } = this.options
    const make = this.options.socket ?? ((u: string) => new WebSocket(u) as unknown as SocketLike)
    const socket = (this.socket = make(url))
    return new Promise<Welcome>((resolve, reject) => {
      socket.onopen = () => {
        const id = this.nextId++
        this.pending.set(id, { resolve, reject })
        socket.send(JSON.stringify({ id, method: 'hello', params: { user, password, create } }))
      }
      socket.onmessage = (event) => this.receive(String(event.data))
      socket.onclose = (event) => {
        this.closed = true
        const error = new ProtocolError('closed', `the connection closed (${event.code})`)
        reject(error) // no effect once the welcome has come; before it, nobody is left waiting for ever
        for (const waiting of this.pending.values()) waiting.reject(error)
        this.pending.clear()
        for (const handler of this.closeHandlers) handler(event.code, this.requestedClose)
      }
    })
  }

  request<T = any>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (!this.socket || this.closed) return Promise.reject(new ProtocolError('closed', 'not connected'))
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
    let frame: any
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
    else waiting.reject(new ProtocolError(frame.error?.code ?? 'internal', frame.error?.message ?? 'request failed'))
  }
}

/** `ws(s)://host/api/docs/<id>/ws` for the page's own server (or for the server named by `?server=` in dev). */
export function socketUrl(doc: string, page: { protocol: string; host: string }): string {
  const scheme = page.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${page.host}/api/docs/${encodeURIComponent(doc)}/ws`
}

/** What a close code of the handshake means for the person. */
export function closeMessage(code: number): string {
  switch (code) {
    case 4400:
      return 'The server did not understand the request.'
    case 4401:
      return 'The name or password is not right.'
    case 4403:
      return 'This page is not allowed to use that server.'
    case 4404:
      return 'There is no such document.'
    case 4408:
      return 'The server did not hear from the page in time.'
    case 1013:
      return 'The document is full, or the connection was too slow.'
    default:
      return 'The connection to the server was lost.'
  }
}
