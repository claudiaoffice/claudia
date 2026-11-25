// The logic of the shell page: the page that Neutralino itself serves (apps/<app>/index.html), which is the only
// page in the window that has Neutralino. It builds the native menu, shows the Claudia web app (local or remote) in
// a full-window frame, talks to the web app with `postMessage` (the shell contract, via bridge.ts) and to the native
// core (the Node extension, core.ts) through Neutralino. Decision D251: Neutralino cannot be injected into a page it
// did not serve (spikes 1-5), so the web app is *framed* by a page that it did.
//
// Everything real (Neutralino, the frame, the window) is handed in, so this is tested with fakes
// (tests/shell-page.test.ts); shell-page-entry.ts is the thin wiring to the real ones.
//
// What the frame can and cannot do: the web app is another origin, so it cannot reach this page's `Neutralino`
// object or its token. It can only post messages, and this page accepts them only from its own frame and only from
// the origin that the core told it to show.

import { Bridge } from './bridge.js'
import { CORE_ID, FROM_CORE, TO_CORE, isCoreMessage } from './core-protocol.js'
import { CONNECT_FAILED_CODES, type ConnectFailedCode } from './contract.js'
import type { CoreMessage, CoreRequest } from './core.js'
import type { App } from './identity.js'
import type { WindowMenuItem } from './menu.js'
import { applyActionStates, routeMenuClick, type ActionState, type KnownAction } from './menu-actions.js'
import { pagePlatform, type PagePlatform } from './platform/page.js'

export interface NeutralinoLike {
  init(): void
  app: { exit(code?: number): Promise<unknown> }
  window: {
    setMainMenu(items: WindowMenuItem[]): Promise<unknown>
  }
  events: { on(event: string, handler: (event: { detail: unknown }) => void): Promise<unknown> }
  extensions: {
    dispatch(id: string, event: string, data: unknown): Promise<unknown>
    /** Which extensions Neutralino has started and which have connected; only used for the log. */
    getStats?(): Promise<unknown>
  }
}

export interface FrameLike {
  src: string
  readonly contentWindow: { postMessage(data: string, targetOrigin: string): void } | null
  addEventListener(type: 'load', listener: () => void): void
  /** Give the frame the keyboard focus (a native menu leaves it with the shell page). */
  focus?(): void
}

/** The overlay that says what is going on while there is no web page to show (starting, connecting, failed). */
export interface StatusView {
  show(title: string, details: string | undefined, error: boolean): void
  hide(): void
}

export interface PageEnv {
  app: App
  version: string
  /** The process of the window (`NL_PID` on the page): the core ends with it (CODE-97, D753). */
  windowPid?: number
  /** The native menu, as `menu.ts` built it for this app. */
  menu: readonly WindowMenuItem[]
  /** The short menu of the front page (sheet 11); without it the whole menu is always shown. */
  startMenu?: readonly WindowMenuItem[]
  neutralino: NeutralinoLike
  frame: FrameLike
  status: StatusView
  /** Register for the window's `message` events. */
  onWindowMessage: (listener: (event: { source: unknown; origin: string; data: unknown }) => void) => void
  locale?: string
  sleep?: (ms: number) => Promise<void>
  /** Runs `action` once after `ms` (the watch over the core's first answer); `setTimeout` by default. */
  after?: (ms: number, action: () => void) => void
  log?: (message: string) => void
  /** What this operating system does differently (src/platform/page.ts); this build's by default. */
  platform?: PagePlatform
}

/** The actions a menu has, and which of them are tick marks. */
export function knownActions(menu: readonly WindowMenuItem[]): KnownAction[] {
  const found: KnownAction[] = []
  const walk = (items: readonly WindowMenuItem[]): void => {
    for (const item of items) {
      if (item.id !== undefined) found.push({ id: item.id, checkable: item.isChecked !== undefined })
      if (item.menuItems) walk(item.menuItems)
    }
  }
  walk(menu)
  return found
}

/** A code the contract defines; anything else is reported as `unreachable`, the most general of them. */
function connectFailedCode(code: string): ConnectFailedCode {
  return (CONNECT_FAILED_CODES as readonly string[]).includes(code) ? (code as ConnectFailedCode) : 'unreachable'
}

const START_ATTEMPTS = 75
const START_PAUSE_MS = 200
/** After Neutralino accepted the first `start`, it is sent again every second until the core has said anything (a
 * request that was accepted is not necessarily one that was heard), and for this many seconds. */
const WATCH_PAUSE_MS = 1000
const WATCH_SECONDS = 20
/** How long a loaded page may take to say hello before the log says that it did not. */
const HELLO_WAIT_MS = 5000

export class ShellPage {
  private menu: WindowMenuItem[]
  /** Which menu is shown: the front page's short one (first, before any page) or a document's whole one. */
  private view: 'start' | 'document' = 'start'
  private readonly known: KnownAction[]
  private readonly checked: Record<string, boolean> = {}
  private readonly bridge: Bridge
  /** The origin of the web app in the frame; messages from any other are refused. `null` while no page is shown. */
  private frameOrigin: string | null = null
  /** The setup code the core sent with the server shown now: its own server's, for its settings pages (D1373). */
  private setupCode: string | undefined
  private menuPending = false
  /** Has the core said anything yet? Until then the page cannot know that it is there at all. */
  private coreSeen = false
  private readonly platform: PagePlatform

  constructor(private readonly env: PageEnv) {
    this.platform = env.platform ?? pagePlatform()
    this.menu = (env.startMenu ?? env.menu).map((item) => structuredClone(item))
    this.known = knownActions(env.menu.map((item) => structuredClone(item))) // the whole menu knows every action
    this.bridge = new Bridge({
      app: env.app,
      known: this.known,
      shell: { name: 'neutralino', platform: this.platform.id, version: env.version },
      send: (raw) => {
        if (this.frameOrigin !== null) this.env.frame.contentWindow?.postMessage(raw, this.frameOrigin)
      },
      ...(env.locale !== undefined ? { locale: env.locale } : {}),
      onStates: (states) => this.applyStates(states),
      onReady: () => {
        this.showView(this.bridge.view)
        this.env.status.hide()
        this.ask({ kind: 'want_servers' })
      },
      onConnect: (address) => this.ask({ kind: 'connect', address }),
      onServers: (servers) => this.ask({ kind: 'servers', servers }),
      // D501, D502: the core shows the dialogs and reads and writes the files; this page only passes the pieces on.
      setupCode: () => this.setupCode,
      files: {
        pick: (request, accept, title) => this.ask({ kind: 'pick_file', request, accept, ...(title !== undefined ? { title } : {}) }),
        begin: (request, name, size, purpose) => this.ask({ kind: 'save_begin', request, name, size, purpose }),
        chunk: (request, index, data) => this.ask({ kind: 'save_chunk', request, index, data }),
        done: (request, chunks) => this.ask({ kind: 'save_done', request, chunks }),
      },
    })
  }

  private log(message: string): void {
    this.env.log?.(message)
  }

  /** Start: Neutralino, the native menu, the listeners, and then the core. */
  async start(): Promise<void> {
    const { neutralino, frame, status } = this.env
    neutralino.init()
    // Closing the window ends the app only through this page (D506, on Windows too since D660), so this listener comes
    // first: a window that is still starting, or whose core never answers, can be closed all the same.
    await neutralino.events.on('windowClose', () => this.quit())
    // The listeners come before anything that can make them fire.
    this.env.onWindowMessage((event) => this.onFrameMessage(event))
    frame.addEventListener('load', () => {
      if (this.frameOrigin === null) return
      status.hide()
      this.watchHello(this.frameOrigin)
    })
    await neutralino.events.on(FROM_CORE, (event) => this.onCore(event.detail))
    await neutralino.events.on('mainMenuItemClicked', (event) => this.onMenuClick(event.detail))
    status.show('Starting…', undefined, false)
    await this.setMenu()
    if (await this.startCore()) this.watchCore(1)
  }

  /** A page that does not say `hello` shortly after it has loaded does not speak the shell contract over `postMessage`:
   * typically a server whose web app is older than the framed-page support (web commit 55a9742). It still works as a web
   * page, but it keeps its own menu bar and the native menu cannot drive it; the console says why, because nothing on
   * the screen does. */
  private watchHello(origin: string): void {
    const after = this.env.after ?? ((ms, action) => void setTimeout(action, ms))
    after(HELLO_WAIT_MS, () => {
      if (this.frameOrigin !== origin || this.bridge.ready) return
      this.log(
        `the page from ${origin} has not said hello in ${HELLO_WAIT_MS / 1000} seconds: its web app probably predates the ` +
          'shell contract over postMessage (it needs the web build of commit 55a9742 or newer), so the native menu cannot drive it',
      )
    })
  }

  private async setMenu(): Promise<void> {
    try {
      await this.env.neutralino.window.setMainMenu(this.menu)
    } catch (problem) {
      this.log(`the native menu could not be set: ${(problem as Error).message}`)
    }
  }

  /** The core is started by Neutralino with the window and connects a moment later; asking too early is refused. */
  private async startCore(): Promise<boolean> {
    const sleep = this.env.sleep ?? ((ms) => new Promise<void>((resolve) => setTimeout(resolve, ms)))
    for (let attempt = 0; attempt < START_ATTEMPTS; attempt++) {
      try {
        await this.dispatch({ kind: 'start', ...(this.env.windowPid ? { windowPid: this.env.windowPid } : {}) })
        return true
      } catch (problem) {
        this.log(`the core is not there yet (${(problem as Error).message})`)
        await sleep(START_PAUSE_MS)
      }
    }
    this.env.status.show(
      'Claudia could not start',
      "The helper process that runs Claudia's local parts did not answer. Close this window and try again.",
      true,
    )
    return false
  }

  /** The core answers a `start` with a status or a page to show. If nothing has come after a second, the request
   * may have gone nowhere (or the core is not running), so it is asked again -- `start` is idempotent -- and after
   * 20 seconds the window says where to look rather than staying on "Starting…" for ever. */
  private watchCore(attempt: number): void {
    const after = this.env.after ?? ((ms, action) => void setTimeout(action, ms))
    after(WATCH_PAUSE_MS, () => {
      if (this.coreSeen) return
      this.logStats()
      if (attempt >= WATCH_SECONDS) {
        this.log(`the core has not answered in ${WATCH_SECONDS} seconds`)
        this.env.status.show(
          'Claudia could not start',
          `The helper process that runs Claudia's local parts has not answered in ${WATCH_SECONDS} seconds.\n` +
            `${this.platform.whereTheLogsAre(this.env.app)}\n${this.platform.howToSeeTheConsole}`,
          true,
        )
        return
      }
      this.ask({ kind: 'start' })
      this.watchCore(attempt + 1)
    })
  }

  private logStats(): void {
    const getStats = this.env.neutralino.extensions.getStats
    if (getStats === undefined) return
    getStats
      .call(this.env.neutralino.extensions)
      .then((stats) => this.log(`extensions: ${JSON.stringify(stats)}`))
      .catch((problem: Error) => this.log(`extensions.getStats failed: ${problem.message}`))
  }

  private dispatch(request: CoreRequest): Promise<unknown> {
    return this.env.neutralino.extensions.dispatch(CORE_ID, TO_CORE, request)
  }

  private ask(request: CoreRequest): void {
    this.dispatch(request).catch((problem: Error) => this.log(`the core did not take '${request.kind}': ${problem.message}`))
  }

  // ----------------------------------------------------------------------------------------------- the core

  private onCore(detail: unknown): void {
    if (!isCoreMessage(detail)) {
      this.log('ignored a message of the core that is not one')
      return
    }
    this.coreSeen = true
    this.handleCore(detail)
  }

  private handleCore(message: CoreMessage): void {
    switch (message.kind) {
      case 'show': {
        this.bridge.reset()
        this.frameOrigin = new URL(message.origin).origin
        this.setupCode = message.setupCode
        this.env.status.show('Opening…', undefined, false)
        this.env.frame.src = `${this.frameOrigin}/`
        return
      }
      case 'status':
        this.env.status.show(message.title, message.details, message.error)
        return
      case 'servers':
        this.bridge.sendServers(message.servers) // a page that is not there yet asks (hello) when it is
        return
      case 'connect_failed':
        if (!this.bridge.sendConnectFailed(connectFailedCode(message.code), message.message)) {
          // nobody is there to tell (the window has no page yet), so it is said here
          this.env.status.show('Cannot connect', message.message, true)
        }
        return
      case 'file_result': {
        const { request, outcome, kind: _kind, ...details } = message
        this.bridge.sendFileResult(request, outcome, details)
        return
      }
      case 'file_chunk':
        this.bridge.sendFileChunk(message.request, message.index, message.data)
        return
      case 'file_done':
        this.bridge.sendFileDone(message.request, message.chunks)
        return
    }
  }

  // ----------------------------------------------------------------------------------------------- the frame

  private onFrameMessage(event: { source: unknown; origin: string; data: unknown }): void {
    if (event.source !== this.env.frame.contentWindow || event.source === null) return
    if (this.frameOrigin === null || event.origin !== this.frameOrigin) {
      this.log(`refused a message from ${event.origin}: it is not the page that was opened (${this.frameOrigin})`)
      return
    }
    if (typeof event.data !== 'string') return
    this.bridge.receive(event.data)
  }

  // ------------------------------------------------------------------------------------------------ the menu

  private onMenuClick(detail: unknown): void {
    const id = typeof detail === 'object' && detail !== null ? (detail as { id?: unknown }).id : undefined
    if (typeof id !== 'string') return
    if (!this.known.some((a) => a.id === id)) {
      this.log(`a menu item that is not one of ours was clicked: ${id}`)
      return
    }
    const route = routeMenuClick(id, this.known, this.checked)
    if (route.kind === 'quit') {
      this.quit()
      return
    }
    // The page carries the action out where the person sees it (File ▸ Open… puts the cursor in its search field): the
    // frame needs the keyboard focus for that, and a native menu leaves it with this page.
    this.env.frame.focus?.()
    if (!this.bridge.sendAction(route.action, route.target)) {
      this.log(`the menu item '${route.action}' was not sent: the page in the frame has not said hello (there is nobody to do it)`)
    }
  }

  /** End the application: Quit in the menu and the window's close button. The request goes through Neutralino's
   * server, so the native side ends the app from its server thread and not from inside the window's own close
   * handler, where Neutralino 6.8.0 crashes on macOS (CODE-26, D506). Windows closes the same way (D660), so that the
   * two platforms share one config. */
  private quit(): void {
    void this.env.neutralino.app.exit().catch((problem: Error) => this.log(`could not quit: ${problem.message}`))
  }

  /** The front page's short menu or a document's whole one (sheet 11), as the page said in its hello. The page reports
   * its ticks again after hello, so the new menu starts from the manifest's. */
  private showView(view: 'start' | 'document'): void {
    if (view === this.view || this.env.startMenu === undefined) return
    this.view = view
    this.menu = (view === 'start' ? this.env.startMenu : this.env.menu).map((item) => structuredClone(item))
    this.applyStates({})
  }

  private applyStates(states: Record<string, ActionState>): void {
    for (const [id, state] of Object.entries(states)) {
      if (state.checked !== undefined) this.checked[id] = state.checked
    }
    this.menu = applyActionStates(this.menu, states)
    if (this.menuPending) return
    this.menuPending = true
    // Neutralino has no per-item update, only the whole menu again: one call for a burst of states.
    void Promise.resolve().then(async () => {
      this.menuPending = false
      await this.setMenu()
    })
  }
}
