// The presence socket (D434, D445): a page with no document open — the front page — keeps one open to its server, so
// that a server started with `--exit-when-idle` (the desktop apps' shared one) knows it is still in use. It carries
// nothing. A dropped socket is opened again, after 1, 2, 4… seconds and at most every 30, until the page lets go.

export interface PresenceDeps {
  WebSocket: typeof WebSocket
  setTimeout: (run: () => void, ms: number) => unknown
  clearTimeout: (handle: unknown) => void
}

const FIRST_WAIT_MS = 1000
const LONGEST_WAIT_MS = 30000

/** The presence socket of the server at `origin` (`http://…` becomes `ws://…`, `https://…` becomes `wss://…`). */
export function presenceUrl(origin: string): string {
  const url = new URL('/api/presence', origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}

/** Keep the presence socket of `origin` open until the returned function is called. */
export function holdPresence(origin: string, deps?: Partial<PresenceDeps>): () => void {
  const Socket = deps?.WebSocket ?? globalThis.WebSocket
  const later = deps?.setTimeout ?? ((run: () => void, ms: number) => globalThis.setTimeout(run, ms))
  const cancel = deps?.clearTimeout ?? ((handle: unknown) => globalThis.clearTimeout(handle as ReturnType<typeof setTimeout>))
  const url = presenceUrl(origin)
  let socket: WebSocket | null = null
  let timer: unknown = null
  let wait = FIRST_WAIT_MS
  let held = true

  const open = () => {
    timer = null
    if (!held) return
    try {
      socket = new Socket(url)
    } catch {
      socket = null
      again()
      return
    }
    socket.onopen = () => {
      wait = FIRST_WAIT_MS
    }
    socket.onclose = () => {
      socket = null
      again()
    }
  }
  const again = () => {
    if (!held) return
    timer = later(open, wait)
    wait = Math.min(wait * 2, LONGEST_WAIT_MS)
  }

  open()
  return () => {
    held = false
    if (timer !== null) cancel(timer)
    timer = null
    socket?.close()
    socket = null
  }
}
