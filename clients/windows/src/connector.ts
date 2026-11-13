// What a window does when a person asks it to connect to a server (E5.8). Port of clients/linux/src/claudia_shell_
// gtk/connector.py. Everything environment-specific -- how a window switches, how a refusal reaches the page -- is
// handed in.
//
// The page asks with the shell contract's `connect` message (or the person types `--server` on the command line);
// `Connector` runs the checks of connection.ts, and in the end either **switches the window to the server** and
// remembers it in the list of this app, or reports *why not* with one of the codes of the contract's
// `connect_failed` message. The newest request wins: an older one that finishes later is dropped.
//
// `ServerBook` is the list of servers that this window's app remembers (servers.ts, settings.ts) as the page sees it:
// this computer's own server first when there is one, then the remembered ones.

import { check as defaultCheck, type Outcome } from './connection.js'
import { AddressRefused, forPage, parseAddress, remember, sanitize, type Address, type Entry } from './servers.js'
import type { Settings } from './settings.js'

export class ServerBook {
  /** The origin of the server this window started (it changes with every start), or `null`. */
  localOrigin: string | null

  constructor(
    private readonly app: string,
    private readonly settings: Settings,
    options: { localOrigin?: string | null; localLabel?: string } = {},
  ) {
    this.localOrigin = options.localOrigin ?? null
    this.localLabel = options.localLabel ?? 'This computer'
  }
  private readonly localLabel: string

  /** The list for the page. */
  entries(): Entry[] {
    return forPage(this.settings.loadServers(this.app), { localOrigin: this.localOrigin, localLabel: this.localLabel })
  }

  /** Keep the list that the page handed back (what is valid of it). */
  replace(raw: unknown): void {
    this.settings.saveServers(this.app, sanitize(raw))
  }

  /** Add the server at `origin` unless it is this computer's own or already there. */
  remember(origin: string): void {
    if (origin === this.localOrigin) return
    this.settings.saveServers(this.app, remember(this.settings.loadServers(this.app), origin))
  }
}

export interface ConnectorOptions {
  book: ServerBook
  /** Show the server at `origin` in the window. */
  switchTo: (origin: string) => void
  /** Report a refusal to the page (or, without a page that hears it, to the window itself). */
  fail: (code: string, message: string) => void
  check?: (address: Address, app: string) => Promise<Outcome>
  log?: (message: string) => void
}

export class Connector {
  private generation = 0
  private readonly check: (address: Address, app: string) => Promise<Outcome>

  constructor(
    private readonly app: string,
    private readonly options: ConnectorOptions,
  ) {
    this.check = options.check ?? ((address, expected) => defaultCheck(address, expected))
  }

  /** Connect to the server that `raw` (an address as a person types it) names. Resolves when this request is
   * finished (also when it was overtaken by a newer one), never rejects. */
  async connect(raw: string): Promise<void> {
    const generation = ++this.generation
    let address: Address
    try {
      address = parseAddress(raw)
    } catch (problem) {
      if (problem instanceof AddressRefused) this.options.fail(problem.code, problem.message)
      else throw problem
      return
    }
    let outcome: Outcome
    try {
      outcome = await this.check(address, this.app)
    } catch (problem) {
      // a bug must not leave the person waiting: say that nothing answered
      this.options.log?.(`checking ${address.origin} failed: ${(problem as Error).stack ?? String(problem)}`)
      outcome = { kind: 'refused', code: 'unreachable', message: `Could not reach ${address.host}.` }
    }
    if (generation !== this.generation) return // the person has asked for something else in the meantime
    if (outcome.kind === 'reached') {
      this.options.book.remember(outcome.origin)
      this.options.switchTo(outcome.origin)
    } else {
      this.options.fail(outcome.code, outcome.message)
    }
  }
}
