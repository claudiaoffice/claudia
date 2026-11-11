// The shell's side of the conversation with the web page (shell contract, E5.12), without Neutralino or a DOM: the
// TypeScript counterpart of clients/linux/src/claudia_shell_gtk/bridge.py. The shell page gives it a `send`
// function (which hands text to the frame) and feeds it every message the page posts. The page is not trusted to be
// well behaved: its messages are checked against the contract, only the page-to-shell types are accepted from it,
// and a state report may only name actions that the menu has.

import * as contract from './contract.js'
import { ContractError, UnknownMessageType, type Message, type ServerEntry, type ShellInfo } from './contract.js'
import type { App } from './identity.js'
import type { ActionState, KnownAction } from './menu-actions.js'

/** What every shell offers the page: it shows the menus itself, and it sends `action` messages for them. A shell
 * that can also connect to another server adds `connect`, and one that keeps the list of servers adds `servers`,
 * each only when the owner of the bridge gave it something to do it with. */
const BASE_CAPABILITIES = ['native-menu', 'actions'] as const

export interface BridgeOptions {
  app: App
  known: readonly KnownAction[]
  shell: ShellInfo
  /** Hands one message (JSON text) to the page. */
  send: (raw: string) => void
  locale?: string
  onStates?: (states: Record<string, ActionState>) => void
  /** The page said hello and the shell welcomed it. */
  onReady?: () => void
  onConnect?: (address: string) => void
  onServers?: (servers: unknown[]) => void
}

export class Bridge {
  private isReady = false
  /** What the page reported as wrong with the shell's messages, for the log and the diagnostics. */
  readonly pageErrors: string[] = []

  constructor(private readonly options: BridgeOptions) {}

  get ready(): boolean {
    return this.isReady
  }

  /** Forget the page (the frame is loading another one). */
  reset(): void {
    this.isReady = false
  }

  // ------------------------------------------------------------------------------------------ from the page

  /** Handle one message that the page posted. */
  receive(raw: string): void {
    let message: Message
    try {
      message = contract.parse(raw)
    } catch (problem) {
      if (problem instanceof UnknownMessageType) return // additive evolution: a newer page may say more than we know
      if (problem instanceof ContractError) return this.reply(contract.errorFor(problem))
      throw problem
    }
    switch (message.type) {
      case 'hello':
        return this.hello(message)
      case 'action_state':
        return this.states(message)
      case 'error':
        this.pageErrors.push(`${String(message.code)}: ${String(message.message)}`)
        return
      case 'connect':
        return this.connect(message)
      case 'servers':
        return this.servers(message)
      default:
        return this.reply(contract.error('bad_message', `'${message.type}' is sent by the shell, not by the page`))
    }
  }

  private hello(message: Message): void {
    const app = this.options.app
    if (message.app !== undefined && message.app !== app) {
      return this.reply(contract.error('bad_message', `this shell shows ${app}, the page shows ${String(message.app)}`))
    }
    let version: number
    try {
      version = contract.negotiate(message)
    } catch (problem) {
      if (problem instanceof ContractError) return this.reply(contract.errorFor(problem))
      throw problem
    }
    this.isReady = true
    this.reply(
      contract.welcome({
        shell: this.options.shell,
        capabilities: this.capabilities(),
        contract: version,
        ...(this.options.locale !== undefined ? { locale: this.options.locale } : {}),
      }),
    )
    this.options.onReady?.()
  }

  capabilities(): string[] {
    return [
      ...BASE_CAPABILITIES,
      ...(this.options.onConnect ? ['connect'] : []),
      ...(this.options.onServers ? ['servers'] : []),
    ]
  }

  private connect(message: Message): void {
    if (!this.isReady) return this.reply(contract.error('bad_message', "say 'hello' before asking to connect"))
    if (!this.options.onConnect) {
      return this.reply(contract.error('bad_message', 'this shell cannot connect to another server'))
    }
    this.options.onConnect(String(message.address))
  }

  private servers(message: Message): void {
    if (!this.isReady) return this.reply(contract.error('bad_message', "say 'hello' before sending the servers"))
    this.options.onServers?.(message.servers as unknown[])
  }

  private states(message: Message): void {
    if (!this.isReady) {
      return this.reply(contract.error('bad_message', "say 'hello' before reporting action states"))
    }
    const known = new Set(this.options.known.map((a) => a.id))
    const states = message.states as Record<string, ActionState>
    const applied: Record<string, ActionState> = {}
    const unknown: string[] = []
    for (const [name, state] of Object.entries(states)) {
      if (known.has(name)) applied[name] = state
      else unknown.push(name)
    }
    if (Object.keys(applied).length > 0) this.options.onStates?.(applied)
    if (unknown.length > 0) {
      this.reply(contract.error('unknown_action', `no such action: ${unknown.sort().join(', ')}`))
    }
  }

  // -------------------------------------------------------------------------------------------- to the page

  /** Tell the page to carry out a menu action. `false` when the page is not there to do it. */
  sendAction(actionId: string, target?: string): boolean {
    if (!this.options.known.some((a) => a.id === actionId)) throw new Error(`no such action: ${actionId}`)
    if (!this.isReady) return false
    this.reply(contract.action(actionId, target))
    return true
  }

  /** Send the page the list of servers. `false` when the page is not there (not yet, or reloading). */
  sendServers(entries: readonly ServerEntry[]): boolean {
    if (!this.isReady) return false
    this.reply(contract.servers(entries))
    return true
  }

  /** Tell the page why the connection it asked for was not made. `false` when the page is not there any more. */
  sendConnectFailed(code: contract.ConnectFailedCode, message: string): boolean {
    if (!this.isReady) return false
    this.reply(contract.connectFailed(code, message))
    return true
  }

  private reply(message: Message): void {
    this.options.send(JSON.stringify(message))
  }
}
