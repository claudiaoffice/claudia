// The page's side of the shell contract (E5.12, `clients/contract/shell-contract.v1.schema.json`), D121: the web app
// speaks it directly instead of being driven through the DOM by `shim.js`, which this replaces.
//
// `window.__claudiaShell.receive(raw)` is the one thing a shell is allowed to assume exists (`webpage.py`'s `send()`
// calls exactly that, unchanged by this file); `window.webkit.messageHandlers.claudia.postMessage(raw)` is the one
// thing this file assumes the shell set up. Neither exists in a plain browser tab, so `ShellBridge` works there too:
// it just never becomes `ready` and `nativeMenu` stays `false`.

export const SHELL_CONTRACT_VERSION = 1
export type App = 'composes' | 'computes' | 'creates'
/** The one display name each app goes by, shared so a browser tab's title and the About dialog never drift
 * apart the way the web and Linux About dialogs once did (D28). */
export const APP_NAME: Record<App, string> = {
  composes: 'Claudia Composes',
  computes: 'Claudia Computes',
  creates: 'Claudia Creates',
}

/** The browser tab's title for the session's own app, or the generic fallback before one has opened (or for
 * anything not one of the three known apps -- `app` is a plain string at this boundary, not the narrower `App`
 * union, the same way `TopBar.vue`'s own `state.app || 'claudia'` treats it). */
export function tabTitle(app: string | undefined): string {
  return (app && APP_NAME[app as App]) || 'Claudia'
}
export interface ActionState {
  enabled?: boolean
  checked?: boolean
  label?: string
}
type ActionHandler = (id: string, target?: string) => void

interface MessageSink {
  post(message: Record<string, unknown>): void
}
const NULL_SINK: MessageSink = { post: () => {} }

/** The `window.webkit.messageHandlers.claudia` handler the shell registers, or `null` outside a Claudia shell. */
export function detectHandler(root: typeof globalThis = globalThis): MessageSink | null {
  const handler = (root as any).webkit?.messageHandlers?.claudia
  return handler ? { post: (message) => handler.postMessage(JSON.stringify(message)) } : null
}

/**
 * One page's conversation with its shell. Framework-free (no Vue) so it can be unit-tested with a fake sink; the Vue
 * wiring (making one per workspace, tearing it down, watching reactive state into `reportStates`) lives in the
 * workspace components themselves, the same way `base-session.ts` keeps its reactive state outside of any component.
 */
export class ShellBridge {
  readonly app: App
  ready = false
  capabilities: string[] = []
  /** The last `error` message the shell sent, for the console and for diagnostics. Not thrown: a bad message from a
   * shell we trust is a bug to log, not a reason to stop the document from working. */
  lastError: string | null = null

  private sink: MessageSink
  private handlers = new Set<ActionHandler>()
  private lastReported: Record<string, string> = {}

  constructor(app: App, sink: MessageSink = NULL_SINK) {
    this.app = app
    this.sink = sink
    this.sink.post({ type: 'hello', contract: SHELL_CONTRACT_VERSION, app })
  }

  /** Does the shell draw the menus itself? While true, a workspace should not render its own `MenuBar`. */
  get nativeMenu(): boolean {
    return this.capabilities.includes('native-menu')
  }

  /** Call with whatever the shell hands `window.__claudiaShell.receive`. */
  receive(raw: string): void {
    let message: any
    try {
      message = JSON.parse(raw)
    } catch {
      return // a shell that sends bad JSON is a bug in the shell; there is nothing useful to answer with
    }
    if (message.type === 'welcome') {
      this.ready = true
      this.capabilities = Array.isArray(message.capabilities) ? message.capabilities.map(String) : []
    } else if (message.type === 'action' && typeof message.action === 'string') {
      for (const handler of this.handlers) handler(message.action, message.target)
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
 */
export function createShellBridge(app: App, handler: MessageSink | null = detectHandler()): ShellBridge & { detach: () => void } {
  const bridge = new ShellBridge(app, handler ?? NULL_SINK) as ShellBridge & { detach: () => void }
  if (handler) {
    const receive = (raw: string) => bridge.receive(raw)
    ;(globalThis as any).__claudiaShell = { receive, contract: SHELL_CONTRACT_VERSION }
    bridge.detach = () => {
      if ((globalThis as any).__claudiaShell?.receive === receive) delete (globalThis as any).__claudiaShell
    }
  } else {
    bridge.detach = () => {}
  }
  return bridge
}
