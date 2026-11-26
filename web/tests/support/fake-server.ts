// One fake server for every web test that talks to a session (E11.7).
//
// It stands in for the `Link` of a session (`LinkLike`) and answers like a server of one app, but it is held to the
// server's own description of its protocol (`protocol/<app>.json`, written by `scripts/generate_protocol.py` from
// `MethodTable.describe`, and checked against the server by `tests/test_protocol_generated.py`):
//
// - a request for a method, or with a parameter, that the description does not have is refused the way the server
//   refuses it (`unknown_method`, `bad_request`), and so is a request that leaves out a parameter it requires or
//   sends one of the wrong kind;
// - an event that the description does not have cannot be pushed;
// - and every such refusal is also written down (`violations`) and fails the test when it is over (`setup.ts`), because
//   a session tells the person about a request that failed and carries on: a renamed method must not pass for that.
//
// It answers what a document's opening needs for each app (`opening.ts`), takes the handlers of a test for the rest
// (a handler wins over the opening's answer), records the calls, and pushes events.
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { OPENING } from './opening'
import computes from './protocol/computes.json'
import composes from './protocol/composes.json'
import creates from './protocol/creates.json'

export type AppName = 'computes' | 'composes' | 'creates'

/** What `scripts/generate_protocol.py` writes of one app. */
export interface Description {
  protocol: number
  app: AppName
  events: string[]
  errors: string[]
  methods: Record<string, { write: boolean; params: { name: string; type: string; required: boolean }[] }>
}

export const DESCRIPTIONS: Record<AppName, Description> = {
  computes: computes as Description,
  composes: composes as Description,
  creates: creates as Description,
}

export type Handler = (params: any) => unknown

/** The kinds of parameter the server's own table (`protocol.py`) checks to a JSON type; an app's own kinds are not
 *  checked here (the server does that, and a test of it does too). */
const KINDS: Record<string, (value: unknown) => boolean> = {
  int: (v) => Number.isInteger(v),
  number: (v) => typeof v === 'number',
  bool: (v) => typeof v === 'boolean',
  str: (v) => typeof v === 'string',
  text: (v) => typeof v === 'string',
  revision: (v) => typeof v === 'string',
  dict: (v) => typeof v === 'object' && v !== null && !Array.isArray(v),
  list: (v) => Array.isArray(v),
  regions: (v) => Array.isArray(v),
}

/** The welcome of a document the fake opens, unless a test says otherwise. */
export function welcomeOf(app: AppName, extra: Partial<Welcome> = {}): Welcome {
  return {
    user: 'ann',
    role: 'owner',
    doc: 'plan',
    app,
    branch: 'main',
    revision: 'main:3',
    id: 1,
    color: '#e6194b',
    locale: 'en',
    people: [],
    presence: [],
    checkpoints: [],
    limits: { max_text: 32767 },
    branches: [{ name: 'main', head: 'main:3', active: true, forked_from: null }],
    proposal: null,
    returned: null,
    ...extra,
  }
}

/** Every fake server made in the running test: `setup.ts` looks at them when the test is over. */
export const made: FakeServer[] = []

export class FakeServer implements LinkLike {
  readonly description: Description
  /** What the page sent, in order. */
  calls: { method: string; params: any }[] = []
  /** What this test answers, by method; it wins over what the opening of the app answers. */
  handlers: Record<string, Handler> = {}
  events: EventHandler[] = []
  closers: CloseHandler[] = []
  welcome: Welcome
  /** A connection that is refused (the welcome never comes). */
  failConnect: ProtocolError | null = null
  connects = 0
  closed = false
  /** What was asked of the fake that the server would refuse, in words. */
  violations: string[] = []

  constructor(
    readonly app: AppName,
    options: { welcome?: Partial<Welcome>; handlers?: Record<string, Handler> } = {},
  ) {
    this.description = DESCRIPTIONS[app]
    this.welcome = welcomeOf(app, options.welcome)
    this.handlers = { ...options.handlers }
    made.push(this)
  }

  /** Answer `method` with `answer` (a function of the parameters, or the answer itself). Returns the server, to chain. */
  on(method: string, answer: Handler | unknown): this {
    this.handlers[method] = typeof answer === 'function' ? (answer as Handler) : () => answer
    return this
  }

  /** Make `method` an unknown one for this test, as it is on an older server: the page's own fallback is what is tried. */
  without(method: string): this {
    this.handlers[method] = () => {
      throw new ProtocolError('unknown_method', method)
    }
    return this
  }

  async connect(): Promise<Welcome> {
    this.connects++
    if (this.failConnect) throw this.failConnect
    return this.welcome
  }

  async request(method: string, params: any = {}): Promise<any> {
    this.calls.push({ method, params })
    this.check(method, params)
    const handler = this.handlers[method] ?? this.opening(method)
    if (!handler) throw new ProtocolError('unknown_method', method)
    return handler(params)
  }

  onEvent(handler: EventHandler) {
    this.events.push(handler)
  }

  onClose(handler: CloseHandler) {
    this.closers.push(handler)
  }

  close() {
    this.closed = true
  }

  /** The server sends an event to the page. An event of a name the description does not have is a test that is wrong. */
  push(name: string, data: any = {}) {
    if (!this.description.events.includes(name)) {
      const message = `${this.app} has no event ${JSON.stringify(name)} in its description`
      this.violations.push(message)
      throw new Error(message)
    }
    for (const handler of this.events) handler(name, data)
  }

  /** The connection is lost (not by the page's own asking). */
  drop(code = 1006) {
    for (const handler of this.closers) handler(code, false)
  }

  // ---------------------------------------------------------------------------------------------- what was asked
  /** How many times `method` was asked for. */
  count(method: string): number {
    return this.calls.filter((c) => c.method === method).length
  }

  /** The parameters of the last request of `method`. */
  last(method: string): any {
    return this.calls.filter((c) => c.method === method).at(-1)?.params
  }

  /** The parameters of every request of `method`, in order. */
  sent(method: string): any[] {
    return this.calls.filter((c) => c.method === method).map((c) => c.params)
  }

  /** The names of the requests, in order. */
  methods(): string[] {
    return this.calls.map((c) => c.method)
  }

  // ---------------------------------------------------------------------------------------------- the description
  private opening(method: string): Handler | undefined {
    const answer = OPENING[this.app][method] ?? OPENING.all[method]
    return answer ? (params) => answer(params, this.welcome) : undefined
  }

  /** Hold a request to what the description says of its method, as `MethodTable.bind` does on the server. */
  private check(method: string, params: any) {
    const entry = this.description.methods[method]
    if (!entry) return this.refuse('unknown_method', `${this.app} has no method ${JSON.stringify(method)}`)
    const known = new Set(entry.params.map((p) => p.name))
    for (const name of Object.keys(params ?? {})) {
      if (!known.has(name)) return this.refuse('bad_request', `${method}: unknown parameter ${JSON.stringify(name)}`)
    }
    for (const p of entry.params) {
      const value = params?.[p.name]
      if (value === undefined || (value === null && !p.required)) {
        if (p.required) return this.refuse('bad_request', `${method}: missing parameter ${JSON.stringify(p.name)}`)
        continue
      }
      const fits = KINDS[p.type]
      if (fits && !fits(value)) return this.refuse('bad_request', `${method}: ${p.name} is not a ${p.type}`)
    }
  }

  private refuse(code: string, message: string): never {
    this.violations.push(message)
    throw new ProtocolError(code, message)
  }
}
