// The native core of one window: everything the shell does that is not drawing and not the contract's page side.
// It is the macOS (and Windows) counterpart of clients/linux/src/claudia_shell_gtk/app.py plus the `Connector` wiring in window.py,
// and like them it knows nothing about Neutralino or the page: how a message gets to the shell page is handed in
// (`send`), so the whole thing is tested with fakes.
//
// There are two ways to start (the same two as on Linux):
//  - **the local server** (the default): the window shows a "starting" status at once; the one local server of the
//    three apps is found or started (private-server.ts, D445, E8.5) and the shell page is told to show it when it answers.
//    When the core ends, the server is only let go of: it is shared, and stops by itself when nothing is connected;
//  - **a given server** (`--server URL`): no server is started. The core connects to it like it does when the
//    person types the address into the page, with the same checks -- https, the right app, a certificate that this
//    computer trusts -- and the address is remembered in the server list of this app.
//
// The core runs as a Neutralino *extension* (core-entry.ts): a Node process that Neutralino starts with the window
// and that ends with it, which is what ends the connection that keeps the local server in use even if the window is
// killed -- and so, ten minutes later, the server (D445).

import { homedir } from 'node:os'
import { join } from 'node:path'
import { Connector, ServerBook } from './connector.js'
import type { Outcome } from './connection.js'
import type { FileMessage, FileRequest } from './file-protocol.js'
import { Files, type Dialogs } from './files.js'
import type { AppIdentity } from './identity.js'
import { prepareServer, SetupProblem } from './local-server.js'
import { hostPlatform } from './platform/host.js'
import type { Address, Entry } from './servers.js'
import type { Settings } from './settings.js'

/** The shell page's requests to the core. */
export type CoreRequest =
  | { kind: 'start'; windowPid?: number }
  | { kind: 'connect'; address: string }
  | { kind: 'servers'; servers: unknown }
  | { kind: 'want_servers' }
  | FileRequest

/** What the core tells the shell page. */
export type CoreMessage =
  | { kind: 'show'; origin: string; setupCode?: string }
  | { kind: 'status'; title: string; details?: string; error: boolean }
  | { kind: 'servers'; servers: Entry[] }
  | { kind: 'connect_failed'; code: string; message: string }
  | FileMessage

/** Do `a` and `b` name the same origin (scheme, host and port)? */
function sameOrigin(a: string, b: string): boolean {
  try {
    return new URL(a).origin === new URL(b).origin
  } catch {
    return false
  }
}

export interface ServerLike {
  /** Find or start the server; its address once it answers. */
  start(): Promise<string>
  /** Let go of the server (the window is gone). The server is shared and ends by itself. */
  stop(): Promise<void>
  /** Its setup code while it has no administrator (D1373), read anew at every call. */
  setupCode?(): string | null
}

export interface CoreOptions {
  identity: AppIdentity
  settings: Settings
  /** Tell the shell page something. */
  send: (message: CoreMessage) => void
  /** The server named on the command line, or `null` to start this app's own. */
  given?: Address | null
  serverFactory?: (app: string) => Promise<ServerLike>
  check?: (address: Address, app: string) => Promise<Outcome>
  log?: (message: string) => void
  /** The Open and Save dialogs and the viewer that prints (D501, D502); the operating system's by default. */
  dialogs?: Dialogs
  /** Where a Save dialog starts the first time (the person's Documents folder by default). */
  documents?: string
}

export class Core {
  readonly book: ServerBook
  private readonly connector: Connector
  private readonly files: Files
  private server: ServerLike | null = null
  private started = false
  private stopped = false
  /** What the shell page was told last, so a page that starts again (a reload) is brought up to date. */
  private current: CoreMessage | null = null

  constructor(private readonly options: CoreOptions) {
    this.book = new ServerBook(options.identity.name, options.settings)
    this.connector = new Connector(options.identity.name, {
      book: this.book,
      switchTo: (origin) => this.show(origin),
      fail: (code, message) => this.emit({ kind: 'connect_failed', code, message }),
      check: options.check,
      log: options.log,
    })
    this.files = new Files({
      dialogs: options.dialogs ?? hostPlatform().dialogs(options.log),
      documents: options.documents ?? defaultDocuments(),
      send: (message) => this.emit(message),
      log: options.log,
    })
  }

  private emit(message: CoreMessage): void {
    if (!this.stopped) this.options.send(message)
  }

  /** `emit`, and remember it as what the window shows now. */
  private say(message: CoreMessage): void {
    this.current = message
    this.emit(message)
  }

  /** Show the server at `origin`; its own server with the setup code it has now, for its settings pages (D1373). */
  private show(origin: string): void {
    const own = this.server !== null && this.book.localOrigin !== null && sameOrigin(origin, this.book.localOrigin)
    const code = own ? this.server?.setupCode?.() : null
    this.say({ kind: 'show', origin, ...(code ? { setupCode: code } : {}) })
  }

  private status(title: string, details?: string, error = false): void {
    this.say({ kind: 'status', title, ...(details !== undefined ? { details } : {}), error })
  }

  /** One message from the shell page. */
  handle(request: CoreRequest): void {
    switch (request.kind) {
      case 'start':
        if (this.started) {
          if (this.current !== null) this.emit(this.current)
          return
        }
        this.started = true
        void this.begin()
        return
      case 'connect':
        void this.connector.connect(request.address)
        return
      case 'servers':
        this.book.replace(request.servers)
        return
      case 'want_servers':
        this.emit({ kind: 'servers', servers: this.book.entries() })
        return
      case 'pick_file':
      case 'save_begin':
      case 'save_chunk':
      case 'save_done':
        this.files.handle(request)
        return
    }
  }

  private async begin(): Promise<void> {
    const { identity, given } = this.options
    if (given) {
      this.status(`Connecting to ${given.host}…`)
      await this.connector.connect(given.origin)
      return
    }
    this.status(`Starting ${identity.title}…`)
    try {
      const server = await (this.options.serverFactory ?? ((app) => prepareServer(app, { log: this.options.log })))(identity.name)
      if (this.stopped) return // the window ended while the server was being set up: nothing was started
      this.server = server
      const url = await server.start()
      if (this.stopped) return
      this.book.localOrigin = url // "Private on this computer" in the page's list, from now on
      this.show(url)
    } catch (problem) {
      if (this.stopped) return
      const title =
        problem instanceof SetupProblem ? `${identity.title} cannot start yet` : `${identity.title} could not start its server`
      this.options.log?.(`${title}: ${(problem as Error).message}`)
      this.status(title, (problem as Error).message, true)
    }
  }

  /** Let go of what this core uses. Safe to repeat. */
  async stop(): Promise<void> {
    this.stopped = true
    const server = this.server
    this.server = null
    if (server !== null) await server.stop()
  }
}

/** The person's Documents folder: where a Save dialog starts the first time. */
function defaultDocuments(): string {
  return join(homedir(), 'Documents')
}
