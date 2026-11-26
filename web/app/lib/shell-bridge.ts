// The page's side of the shell contract (E5.12, `clients/contract/shell-contract.v1.schema.json`), D121: the web app
// speaks it directly instead of being driven through the DOM by `shim.js`, which this replaces.
//
// Two ways to reach a shell, both carrying the same JSON text:
//  - the GTK shell (WebKit) sets up `window.webkit.messageHandlers.claudia` and calls
//    `window.__claudiaShell.receive(raw)` (`webpage.py`'s `send()`, unchanged by this file);
//  - the Neutralino shells (macOS, later Windows) show this page in a frame of their own page, so the two talk with
//    `postMessage` (`detectParentSink`): this page posts to its parent window and hears only the parent.
// Neither exists in a plain browser tab, so `ShellBridge` works there too: it just never becomes `ready` and
// `nativeMenu` stays `false`.
import { rememberAskAdministrator, rememberSetupCode } from './setup-code'
import type { WireData } from './protocol'
import { isBookmark, named, type Bookmark } from './server-bookmarks'


export const SHELL_CONTRACT_VERSION = 1
export type App = 'composes' | 'computes' | 'creates'
/** What a page tells its shell it is (sheet 11): the front page, or a document. */
export type ShellView = 'start' | 'document'

/** Is `value` one of the three apps? (`app` is a plain string wherever a server told it.) */
export function isApp(value: unknown): value is App {
  return value === 'composes' || value === 'computes' || value === 'creates'
}
/** The one display name each app goes by, shared so a browser tab's title and the About dialog never drift
 * apart the way the web and Linux About dialogs once did (D28). */
export const APP_NAME: Record<App, string> = {
  composes: 'Claudia Composes',
  computes: 'Claudia Computes',
  creates: 'Claudia Creates',
}

/** The browser tab's title (WCAG 2.4.2): the open document first, then its app, so two tabs of the same app can be
 * told apart; just the app for a document without a name; the generic fallback before one has opened, or for
 * anything not one of the three known apps -- `app` is a plain string at this boundary, not the narrower `App`
 * union, the same way `TopBar.vue`'s own `state.app || 'claudia'` treats it. */
export function tabTitle(app: string | undefined, documentName?: string): string {
  const name = app && APP_NAME[app as App]
  if (!name) return 'Claudia'
  return documentName ? `${documentName} – ${name}` : name
}
export interface ActionState {
  enabled?: boolean
  checked?: boolean
  label?: string
}
type ActionHandler = (id: string, target?: string) => void
type ConnectFailedHandler = (code: string, message: string) => void

/** How much of a file goes into one `file_chunk` (D501): 36 KiB of bytes are 48 KiB of base64, which leaves room in a
 * message of at most 64 KiB. */
export const FILE_CHUNK_BYTES = 36 * 1024
/** The largest file that goes through the shell (D501): a bigger one is refused before anything is sent. */
export const MAX_FILE_BYTES = 100 * 1024 * 1024

/** What became of a file the page handed the shell (D501): saved where the person chose, opened in the computer's own
 * viewer (to print it, D502), or nothing (the person cancelled the Save dialog). */
export type SaveOutcome = { kind: 'saved'; path: string } | { kind: 'opened'; path: string } | { kind: 'cancelled' }
/** Why the page hands the shell a file: to save it where the person says, or to print it (the shell opens it in the
 * computer's viewer for PDFs, which prints, D502). */
export type FilePurpose = 'save' | 'print'

/** The extensions of an `<input accept>` value (`.docx,.odt,image/png` gives `docx`, `odt`): what the shell's dialog
 * offers. A MIME type is left out (a shell's dialog filters by extension), and so is anything that is not a short
 * word. */
export function acceptedExtensions(accept: string): string[] {
  const found: string[] = []
  for (const token of accept.split(',')) {
    const extension = token.trim().toLowerCase()
    if (!extension.startsWith('.')) continue
    const bare = extension.slice(1)
    if (/^[a-z0-9]{1,16}$/.test(bare) && !found.includes(bare)) found.push(bare)
  }
  return found.slice(0, 32)
}

function toBase64(bytes: Uint8Array): string {
  let text = ''
  for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(text)
}

function fromBase64(data: string): Uint8Array {
  const raw = atob(data)
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes
}

/** A file the person chose with the shell's Open dialog (D501), and its full path on this computer when the shell says
 * it (SEC-27: Insert ▸ Image offers to save it with the picture); `null` from a shell that does not. */
export interface PickedFile {
  file: File
  path: string | null
}

/** A file on its way from the shell to the page, or from the page to the shell. */
interface Transfer {
  /** `pick`: chunks arrive and the promise gets a `PickedFile`; `save`: the shell answers with where it went; `offer`: a
   * file the person dropped on the window, which the shell sends unasked (D505). */
  kind: 'pick' | 'save' | 'offer'
  name: string
  size: number
  /** Where a picked file is on this computer, if the shell said. */
  path?: string
  chunks: Uint8Array[]
  resolve: (value: never) => void
  reject: (problem: Error) => void
}

interface MessageSink {
  post(message: Record<string, unknown>): void
  /** For a shell that does not call `window.__claudiaShell.receive` itself: start passing what the shell sends to
   * `receive`; returns the function that stops it. */
  listen?(receive: (raw: string) => void): () => void
}
const NULL_SINK: MessageSink = { post: () => {} }

/** Where a WebKit shell registers its handler, and where this page leaves its own entry point for the shell. */
type WebKitRoot = { webkit?: { messageHandlers?: { claudia?: { postMessage(message: string): void } } } }
type ShellRoot = typeof globalThis & { __claudiaShell?: { receive: (raw: string) => void; contract: number } }

/** The `window.webkit.messageHandlers.claudia` handler the shell registers, or `null` outside a Claudia shell. */
export function detectHandler(root: typeof globalThis = globalThis): MessageSink | null {
  const handler = (root as WebKitRoot).webkit?.messageHandlers?.claudia
  return handler ? { post: (message) => handler.postMessage(JSON.stringify(message)) } : null
}

/** Origins a Neutralino shell page can have: its own static server on this computer, plain http, any port. */
export function isShellOrigin(origin: string): boolean {
  try {
    const url = new URL(origin)
    return url.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)
  } catch {
    return false
  }
}

/** The sink for a page that a shell shows in a frame (`null` when the page is the top window, as in a browser tab).
 * Messages go to the parent window; they hold nothing secret, and the page cannot know the parent's port before the
 * parent has answered, so the target origin is `*`. What the page *accepts* is strict: only text from the parent
 * window itself, and only when the parent is a page on this computer's loopback (the shell's own). */
export function detectParentSink(root: typeof globalThis = globalThis): MessageSink | null {
  const win = root as unknown as Window
  if (!win.parent || win.parent === win) return null
  return {
    post: (message) => win.parent.postMessage(JSON.stringify(message), '*'),
    listen: (receive) => {
      const onMessage = (event: MessageEvent) => {
        if (event.source !== win.parent || typeof event.data !== 'string' || !isShellOrigin(event.origin)) return
        receive(event.data)
      }
      win.addEventListener('message', onMessage)
      return () => win.removeEventListener('message', onMessage)
    },
  }
}

/**
 * One page's conversation with its shell. Framework-free (no Vue) so it can be unit-tested with a fake sink; the Vue
 * wiring (making one per workspace, tearing it down, watching reactive state into `reportStates`) lives in the
 * workspace components themselves, the same way `base-session.ts` keeps its reactive state outside of any component.
 */
export class ShellBridge {
  /** The app this page shows, or `undefined` while it does not know yet (a server that asks for a secret before it
   * says which app it runs): the shell, which was connected to a server of its own app, takes it to be that. */
  readonly app: App | undefined
  ready = false
  capabilities: string[] = []
  /** The app the shell's window is (D444, `welcome.app`), or `null`: a browser tab, or a shell that does not say. On a
   * server of several apps the front page then shows this app only. */
  windowApp: App | null = null
  /** The servers this shell remembers for its app, or `null` until the shell has sent the list (the shell owns it:
   * the page's `localStorage` is per origin and so cannot hold a list that spans servers). */
  servers: Bookmark[] | null = null
  /** The last `error` message the shell sent, for the console and for diagnostics. Not thrown: a bad message from a
   * shell we trust is a bug to log, not a reason to stop the document from working. */
  lastError: string | null = null

  private sink: MessageSink
  private transfers = new Map<string, Transfer>()
  private requests = 0
  private handlers = new Set<ActionHandler>()
  private offerHandlers = new Set<(file: File) => void>()
  private failureHandlers = new Set<ConnectFailedHandler>()
  private lastReported: Record<string, string> = {}

  /** `view` (sheet 11): the front page gets the shell's short menu, a document the whole one. */
  constructor(app: App | undefined, sink: MessageSink = NULL_SINK, view?: ShellView) {
    this.app = app
    this.sink = sink
    this.sink.post({ type: 'hello', contract: SHELL_CONTRACT_VERSION, ...(app ? { app } : {}), ...(view ? { view } : {}) })
  }

  /** Does the shell draw the menus itself? While true, a workspace should not render its own `MenuBar`. */
  get nativeMenu(): boolean {
    return this.capabilities.includes('native-menu')
  }

  /** Can the shell connect this window to another server of the same app (instead of the page navigating there)? */
  get canConnect(): boolean {
    return this.ready && this.capabilities.includes('connect')
  }

  /** Does the shell keep the list of servers (so the page shows and changes that one, not its own)? */
  get hasServerList(): boolean {
    return this.ready && this.capabilities.includes('servers')
  }

  /** Does the shell choose files on this computer and save files there, with its own dialogs (D501)? A web view in a
   * desktop window may show no file picker for `<input type="file">` (WKWebView in Neutralino does not), cannot open
   * one from a menu item at all, and saves a download to some folder without asking. */
  get handlesFiles(): boolean {
    return this.ready && this.capabilities.includes('files')
  }

  private nextRequest(): string {
    this.requests += 1
    return `f${this.requests}-${Math.random().toString(36).slice(2, 8)}`
  }

  /** Ask the shell for a file of this computer, with its own Open dialog showing the `extensions` (D501). `null` when
   * the person cancelled; an `Error` with a message for the person when the shell could not read it. */
  pickFile(extensions: readonly string[], title?: string): Promise<PickedFile | null> {
    const request = this.nextRequest()
    return new Promise<PickedFile | null>((resolve, reject) => {
      this.transfers.set(request, { kind: 'pick', name: '', size: 0, chunks: [], resolve: resolve as (value: never) => void, reject })
      this.sink.post({ type: 'pick_file', request, accept: [...extensions], ...(title ? { title } : {}) })
    })
  }

  /** Hand the shell `blob` to save as `name` on this computer: it asks where with its own Save dialog (D501). With
   * `purpose` `print` it asks nothing and opens the file in the computer's viewer for its kind instead (D502). */
  async saveFile(name: string, blob: Blob, purpose: FilePurpose = 'save'): Promise<SaveOutcome> {
    if (blob.size > MAX_FILE_BYTES) throw new Error(`the file is larger than ${MAX_FILE_BYTES / 1024 / 1024} MB`)
    const bytes = new Uint8Array(await blob.arrayBuffer())
    const request = this.nextRequest()
    const answer = new Promise<SaveOutcome>((resolve, reject) => {
      this.transfers.set(request, { kind: 'save', name, size: bytes.length, chunks: [], resolve: resolve as (value: never) => void, reject })
    })
    this.sink.post({
      type: 'save_file',
      request,
      name,
      size: bytes.length,
      ...(blob.type ? { mime: blob.type.slice(0, 128) } : {}),
      ...(purpose === 'print' ? { purpose } : {}),
    })
    let index = 0
    for (let at = 0; at < bytes.length; at += FILE_CHUNK_BYTES) {
      this.sink.post({ type: 'file_chunk', request, index, data: toBase64(bytes.subarray(at, at + FILE_CHUNK_BYTES)) })
      index += 1
    }
    this.sink.post({ type: 'file_done', request, chunks: index })
    return answer
  }

  /** The shell starts sending a dropped file (D505): its pieces come like those of a picked file. */
  private offered(message: WireData): void {
    if (typeof message.request !== 'string' || this.transfers.has(message.request)) return
    const size = typeof message.size === 'number' ? message.size : 0
    const name = typeof message.name === 'string' ? message.name : 'file'
    if (size > MAX_FILE_BYTES) return console.warn('[claudia shell] a dropped file is too large:', name)
    const deliver = (file: File) => {
      for (const handler of this.offerHandlers) handler(file)
    }
    this.transfers.set(message.request, {
      kind: 'offer',
      name,
      size,
      chunks: [],
      resolve: deliver as (value: never) => void,
      reject: (problem) => console.warn('[claudia shell] a dropped file did not arrive:', problem.message),
    })
  }

  private fileMessage(message: WireData): void {
    if (message.type === 'offer_file') return this.offered(message)
    const transfer = typeof message.request === 'string' ? this.transfers.get(message.request) : undefined
    if (!transfer) return
    const request = message.request as string
    const fail = (text: string) => {
      this.transfers.delete(request)
      transfer.reject(new Error(text))
    }
    if (message.type === 'file_result') {
      if (message.outcome === 'cancelled') {
        this.transfers.delete(request)
        transfer.resolve((transfer.kind === 'pick' ? null : { kind: 'cancelled' }) as never)
      } else if (message.outcome === 'failed') {
        fail(typeof message.message === 'string' ? message.message : 'the file could not be handled')
      } else if ((message.outcome === 'saved' || message.outcome === 'opened') && transfer.kind === 'save') {
        this.transfers.delete(request)
        const path = typeof message.path === 'string' ? message.path : transfer.name
        transfer.resolve({ kind: message.outcome, path } as never)
      } else if (message.outcome === 'picked' && transfer.kind === 'pick') {
        transfer.name = typeof message.name === 'string' ? message.name : 'file'
        transfer.size = typeof message.size === 'number' ? message.size : 0
        if (typeof message.path === 'string' && message.path) transfer.path = message.path
        if (transfer.size > MAX_FILE_BYTES) fail(`the file is larger than ${MAX_FILE_BYTES / 1024 / 1024} MB`)
      }
    } else if (message.type === 'file_chunk' && transfer.kind !== 'save' && typeof message.data === 'string') {
      if (message.index !== transfer.chunks.length) return fail('a piece of the file went missing on the way')
      try {
        transfer.chunks.push(fromBase64(message.data))
      } catch {
        fail('a piece of the file arrived damaged')
      }
    } else if (message.type === 'file_done' && transfer.kind !== 'save') {
      this.transfers.delete(request)
      const file = new File(transfer.chunks as BlobPart[], transfer.name)
      if (file.size !== transfer.size) return transfer.reject(new Error('the file did not arrive whole'))
      transfer.resolve((transfer.kind === 'pick' ? { file, path: transfer.path ?? null } : file) as never)
    }
  }

  /** Call with whatever the shell hands `window.__claudiaShell.receive`. */
  receive(raw: string): void {
    let message: WireData
    try {
      message = JSON.parse(raw)
    } catch {
      return // a shell that sends bad JSON is a bug in the shell; there is nothing useful to answer with
    }
    if (message.type === 'welcome') {
      this.ready = true
      this.capabilities = Array.isArray(message.capabilities) ? message.capabilities.map(String) : []
      this.windowApp = typeof message.app === 'string' && isApp(message.app) ? message.app : null
      // the setup code of the desktop app's own server, for its settings pages (D1373); never sent for another server
      if (typeof message.setup_code === 'string') rememberSetupCode(message.setup_code, 'app')
      // the computer's shared service, which she may not set up herself: "ask an administrator" (E8.5, D1624)
      rememberAskAdministrator(message.ask_administrator === true)
    } else if (message.type === 'action' && typeof message.action === 'string') {
      for (const handler of this.handlers) handler(message.action, message.target)
    } else if (message.type === 'servers' && Array.isArray(message.servers)) {
      this.servers = message.servers.filter(isBookmark).map((bookmark: Bookmark) => named(bookmark))
    } else if (message.type === 'connect_failed' && typeof message.message === 'string') {
      for (const handler of this.failureHandlers) handler(String(message.code), message.message)
    } else if (['file_result', 'file_chunk', 'file_done', 'offer_file'].includes(String(message.type))) {
      this.fileMessage(message)
    } else if (message.type === 'error') {
      this.lastError = `${message.code}: ${message.message}`
      console.warn('[claudia shell]', this.lastError)
    }
  }

  /** Called when the person chose a menu item in the shell's native menu (or its accelerator). Returns a remover. */
  onAction(handler: ActionHandler): () => void {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  /** Called with a file the person dropped on the window, which the shell took because the web view would not hand it
   * to the page (D505: WebKitGTK, from the file manager). Returns a remover. */
  onFileOffered(handler: (file: File) => void): () => void {
    this.offerHandlers.add(handler)
    return () => this.offerHandlers.delete(handler)
  }

  /** Called when the shell could not connect to the server that `connect` asked for; `message` is fit for the person. */
  onConnectFailed(handler: ConnectFailedHandler): () => void {
    this.failureHandlers.add(handler)
    return () => this.failureHandlers.delete(handler)
  }

  /** Ask the shell to show the server at `address` (as a person typed it, or an origin from the list) in this window.
   * The shell checks it; the answer is a new page, or `onConnectFailed`. */
  connect(address: string): void {
    this.sink.post({ type: 'connect', address })
  }

  /** Hand the shell the list of servers as the person changed it (renamed, say). Nothing is sent before the shell has
   * sent its own list: an empty page must never replace what the shell remembers. */
  sendServers(servers: Bookmark[]): void {
    if (!this.hasServerList || this.servers === null) return
    this.servers = servers
    this.sink.post({ type: 'servers', servers })
  }

  /** Tells the shell which actions are enabled, ticked or relabelled right now. Only what changed is sent. */
  reportStates(states: Record<string, ActionState>): void {
    if (!this.ready) return
    const changed: Record<string, ActionState> = {}
    for (const [id, state] of Object.entries(states)) {
      const key = JSON.stringify(state)
      if (this.lastReported[id] !== key) {
        changed[id] = state
        this.lastReported[id] = key
      }
    }
    if (Object.keys(changed).length) this.sink.post({ type: 'action_state', states: changed })
  }
}

/**
 * Makes the bridge for `app` and, if a shell is present, registers it as `window.__claudiaShell` so the shell can
 * reach it. Call `detach()` when the workspace that made it goes away (closing one document and opening another of a
 * different app must not leave the old bridge answering for the new one).
 *
 * `wrap` lets the caller make the bridge reactive (Vue's `reactive()`, typically) *before* this function hands out
 * `window.__claudiaShell.receive` to the shell: that closure has to call back into whatever object the caller will
 * actually read from (`shell.nativeMenu` in a template), not the plain one underneath it. Calling `reactive()` on
 * the value this function already returns, as the workspace components used to, wraps a *second*, independent
 * bridge instance too late to help -- `receive` still mutates the first, unwrapped one, so a change like `welcome`'s
 * capabilities lands outside Vue's dependency tracking and a template bound to `shell.nativeMenu` is never told to
 * re-render for it (it only shows the right value by accident, on some later render Vue schedules for an unrelated
 * reason). This module otherwise knows nothing about Vue (so `ShellBridge` itself stays unit-testable without it);
 * `wrap` keeps it that way by taking the reactivity function as a plain callback instead of importing one.
 */
/** The bridges of the pages that are there now, newest last: a helper that is not part of any page (saving a file,
 * `download.ts`) asks the newest one. */
const living: ShellBridge[] = []

/** The bridge of the page that is shown now, if the page is in a shell that has said `welcome`; `null` in a browser
 * tab. */
export function currentShell(): ShellBridge | null {
  for (let i = living.length - 1; i >= 0; i--) if (living[i]?.ready) return living[i] ?? null
  return null
}

export function createShellBridge(
  app: App | undefined,
  handler: MessageSink | null = detectHandler() ?? detectParentSink(),
  // Typed as `ShellBridge => ShellBridge`, even though Vue's `reactive()` (the intended `wrap`) actually returns
  // `Reactive<ShellBridge>` -- a type that structurally drops `ShellBridge`'s private fields and so is never
  // assignable back to it. Callers pass an inline `(bridge) => reactive(bridge) as ShellBridge` to paper over that
  // mismatch at the one spot that knows it is safe (the fields are still there at runtime; only the structural
  // check can't see them), rather than this module importing `reactive` itself just to make the types line up.
  wrap: (bridge: ShellBridge) => ShellBridge = (bridge) => bridge,
  view?: ShellView,
): ShellBridge & { detach: () => void } {
  const bridge = wrap(new ShellBridge(app, handler ?? NULL_SINK, view)) as ShellBridge & { detach: () => void }
  if (handler) {
    const receive = (raw: string) => bridge.receive(raw)
    const root = globalThis as ShellRoot
    root.__claudiaShell = { receive, contract: SHELL_CONTRACT_VERSION }
    const stopListening = handler.listen?.(receive)
    living.push(bridge)
    bridge.detach = () => {
      stopListening?.()
      if (root.__claudiaShell?.receive === receive) delete root.__claudiaShell
      const at = living.indexOf(bridge)
      if (at >= 0) living.splice(at, 1)
    }
  } else {
    bridge.detach = () => {}
  }
  return bridge
}
