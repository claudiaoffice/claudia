// The link between a Node process that Neutralino started (an *extension*) and Neutralino itself. This is the
// protocol that spike 5 proved on a real Mac (2026-11-10): Neutralino starts the extension, hands it the port and
// the tokens as one JSON object on stdin, and the extension connects back over a WebSocket
// (`ws://localhost:<port>?extensionId=...&connectToken=...`). The page sends to it with
// `Neutralino.extensions.dispatch(id, event, data)` and it answers with `app.broadcast`, which every page hears as
// `Neutralino.events.on(event, ...)`. When Neutralino closes the connection (the window is gone) the extension ends.
//
// No Neutralino library is needed: the socket is a plain WebSocket (Node 22 has one built in), and the socket class
// is handed in so the tests need no network.

import { randomUUID } from 'node:crypto'

export interface ExtensionAuth {
  nlPort: number
  nlToken: string
  nlConnectToken: string
  nlExtensionId: string
}

export interface SocketLike {
  send(data: string): void
  close(): void
  addEventListener(type: 'open' | 'error' | 'close', listener: () => void): void
  addEventListener(type: 'message', listener: (event: { data: unknown }) => void): void
}

export type SocketFactory = (url: string) => SocketLike

/** The auth object from the extension's stdin, once it has arrived completely (it may come in pieces); `null` until
 * then, and `null` for something that is not what Neutralino sends. The port may be a number or a string of digits
 * (the spike's extension did not check, and a check that is stricter than what Neutralino sends makes the core refuse
 * the tokens it was given and wait for ever); the tokens are strings. */
export function parseAuth(raw: string): ExtensionAuth | null {
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null) return null
  const auth = value as Record<string, unknown>
  const port = typeof auth.nlPort === 'string' && /^\d{1,5}$/.test(auth.nlPort) ? Number(auth.nlPort) : auth.nlPort
  if (
    typeof port !== 'number' ||
    !Number.isInteger(port) ||
    port < 1 ||
    port > 65535 ||
    typeof auth.nlToken !== 'string' ||
    typeof auth.nlConnectToken !== 'string' ||
    typeof auth.nlExtensionId !== 'string'
  ) {
    return null
  }
  return { nlPort: port, nlToken: auth.nlToken, nlConnectToken: auth.nlConnectToken, nlExtensionId: auth.nlExtensionId }
}

/** What arrived on stdin, for the log when it is not accepted: the size and the *shape* (keys and their types), never
 * the values, which are tokens. */
export function describeAuthInput(raw: string): string {
  const size = `${raw.length} characters`
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return `${size}, not (yet) complete JSON`
  }
  if (typeof value !== 'object' || value === null) return `${size}, JSON but ${value === null ? 'null' : typeof value}, not an object`
  const shape = Object.entries(value as Record<string, unknown>).map(([key, item]) => `${key}: ${typeof item}`)
  return `${size}, an object with {${shape.join(', ')}}`
}

export function socketUrl(auth: ExtensionAuth): string {
  return `ws://localhost:${auth.nlPort}?extensionId=${encodeURIComponent(auth.nlExtensionId)}&connectToken=${encodeURIComponent(auth.nlConnectToken)}`
}

export interface LinkHandlers {
  /** An event the page dispatched to this extension. */
  onEvent: (event: string, data: unknown) => void
  /** Neutralino closed the connection (or it never opened): the window is gone. */
  onClosed: () => void
  onOpen?: () => void
  log?: (message: string) => void
}

export class ExtensionLink {
  private readonly socket: SocketLike
  private closed = false

  constructor(
    private readonly auth: ExtensionAuth,
    private readonly handlers: LinkHandlers,
    makeSocket: SocketFactory = (url) => new WebSocket(url) as unknown as SocketLike,
  ) {
    this.socket = makeSocket(socketUrl(auth))
    this.socket.addEventListener('open', () => handlers.onOpen?.())
    // A socket that cannot be opened reports an `error` and, in Node's WebSocket, no `close` at all; the window is
    // gone in both cases, so both end the link (and with it this process).
    const finish = (): void => {
      if (this.closed) return
      this.closed = true
      handlers.onClosed()
    }
    this.socket.addEventListener('error', () => {
      handlers.log?.('the link to Neutralino failed')
      finish()
    })
    this.socket.addEventListener('close', finish)
    this.socket.addEventListener('message', (message) => {
      let body: unknown
      try {
        body = JSON.parse(String(message.data))
      } catch {
        return
      }
      if (typeof body !== 'object' || body === null) return
      const { event, data } = body as { event?: unknown; data?: unknown }
      if (typeof event === 'string') handlers.onEvent(event, data)
    })
  }

  /** Tell every page: they hear it with `Neutralino.events.on(event, ...)`. */
  broadcast(event: string, data: unknown): void {
    if (this.closed) return
    this.socket.send(JSON.stringify({ id: randomUUID(), method: 'app.broadcast', accessToken: this.auth.nlToken, data: { event, data } }))
  }

  close(): void {
    this.closed = true
    this.socket.close()
  }
}
