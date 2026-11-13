// The shell contract, version 1 (E5.12), for the macOS shell: the messages the web page and the shell send each
// other. Port of clients/linux/src/claudia_shell_gtk/contract.py -- the specification is the JSON schema
// clients/contract/shell-contract.v1.schema.json, and tests/contract.test.ts checks that this module and the schema
// accept and refuse the same messages. Plain TypeScript with no Node or browser import, so the shell page (browser)
// and the core (Node) share it.
//
// The page is not trusted to be polite: `parse` checks everything against the contract before anything acts on it.
// Inside a version only additions are made; a message of a type this version does not know is ignored, never
// answered (`UnknownMessageType`).

export const CONTRACT_VERSION = 1
export const SUPPORTED_VERSIONS: readonly number[] = [1]
/** A message longer than this is refused unread. */
export const MAX_MESSAGE_BYTES = 64 * 1024
export const MAX_SERVER_LIST = 64

export const CONNECT_FAILED_CODES = [
  'bad_address',
  'insecure',
  'unreachable',
  'not_claudia',
  'wrong_app',
  'certificate_expired',
  'certificate_invalid',
  'not_trusted',
] as const
export type ConnectFailedCode = (typeof CONNECT_FAILED_CODES)[number]

const ERROR_CODES = ['bad_json', 'bad_message', 'unsupported_contract', 'unknown_action', 'internal'] as const
export type ErrorCode = (typeof ERROR_CODES)[number]

export type Message = { type: string; [key: string]: unknown }

const ACTION_ID = /^[a-z]+(\.[a-z][a-z0-9-]*)+$/
const TOKEN = /^[a-z][a-z0-9-]*$/
const LOCALE = /^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$/
const MAX_ACTION_ID = 64
const MAX_TOKEN = 32
const MAX_TEXT = 512
const MAX_ADDRESS = 255
const MAX_LABEL = 128

/** A message that cannot be accepted. `code` is one of the schema's `error` codes. */
export class ContractError extends Error {
  constructor(
    readonly code: ErrorCode,
    message: string,
    readonly supported?: readonly number[],
  ) {
    super(message)
    this.name = 'ContractError'
  }
}

/** A well-formed message of a type this version does not know. Receivers ignore it (additive evolution). */
export class UnknownMessageType extends Error {
  constructor(readonly messageType: string) {
    super(`unknown message type '${messageType}'`)
    this.name = 'UnknownMessageType'
  }
}

const bad = (what: string): ContractError => new ContractError('bad_message', what)
const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
const isInt = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value)

function text(message: Record<string, unknown>, key: string, limit: number, required = false): void {
  const value = message[key]
  if (value === undefined || value === null) {
    if (required) throw bad(`'${String(message.type)}' needs '${key}'`)
    return
  }
  if (typeof value !== 'string' || value.length > limit) throw bad(`'${key}' is text of at most ${limit} characters`)
}

function token(value: unknown, what: string): void {
  if (!(typeof value === 'string' && value.length <= MAX_TOKEN && TOKEN.test(value))) {
    throw bad(`${what} is a lower case word (letters, digits, hyphens)`)
  }
}

function actionId(value: unknown, what = 'an action'): void {
  if (!(typeof value === 'string' && value.length <= MAX_ACTION_ID && ACTION_ID.test(value))) {
    throw bad(`${what} is named like 'file.save' (lower case, namespaced)`)
  }
}

function version(message: Record<string, unknown>): void {
  const value = message.contract
  if (!isInt(value) || value < 1) throw bad(`'${String(message.type)}' needs 'contract', a whole number from 1`)
}

type Check = (message: Record<string, unknown>) => void

const CHECKS: Record<string, Check> = {
  hello(message) {
    version(message)
    if ('app' in message) token(message.app, "'app'") // a page that does not know its app yet omits it
    text(message, 'frontend', 64)
  },
  welcome(message) {
    version(message)
    const shell = message.shell
    if (!isRecord(shell)) throw bad("'welcome' needs 'shell'")
    token(shell.name, "the shell's name")
    if (!['linux', 'windows', 'macos'].includes(String(shell.platform))) {
      throw bad("the shell's platform is linux, windows or macos")
    }
    text(shell, 'version', 64, true)
    const capabilities = message.capabilities
    if (!Array.isArray(capabilities) || new Set(capabilities.map(String)).size !== capabilities.length) {
      throw bad("'capabilities' is a list of different words")
    }
    for (const capability of capabilities) token(capability, 'a capability')
    const locale = message.locale
    if (locale !== undefined && locale !== null && !(typeof locale === 'string' && locale.length <= 35 && LOCALE.test(locale))) {
      throw bad("'locale' is a BCP-47-ish tag such as 'de' or 'de-DE'")
    }
  },
  action(message) {
    actionId(message.action)
    text(message, 'target', 256)
  },
  action_state(message) {
    const states = message.states
    if (!isRecord(states) || Object.keys(states).length === 0) {
      throw bad("'action_state' needs 'states' with at least one action")
    }
    for (const [name, state] of Object.entries(states)) {
      actionId(name)
      if (!isRecord(state)) throw bad(`the state of ${name} is an object`)
      for (const flag of ['enabled', 'checked']) {
        if (flag in state && typeof state[flag] !== 'boolean') throw bad(`'${flag}' of ${name} is true or false`)
      }
      text(state, 'label', 128)
    }
  },
  error(message) {
    if (!ERROR_CODES.includes(message.code as ErrorCode)) throw bad(`'code' is one of ${ERROR_CODES.join(', ')}`)
    text(message, 'message', MAX_TEXT, true)
    const supported = message.supported
    if (supported !== undefined && supported !== null && !(Array.isArray(supported) && supported.every((v) => isInt(v) && v >= 1))) {
      throw bad("'supported' is a list of contract versions")
    }
  },
  connect(message) {
    text(message, 'address', MAX_ADDRESS, true)
    if (!message.address) throw bad("'connect' needs an address")
  },
  connect_failed(message) {
    if (!CONNECT_FAILED_CODES.includes(message.code as ConnectFailedCode)) {
      throw bad(`'code' is one of ${CONNECT_FAILED_CODES.join(', ')}`)
    }
    text(message, 'message', MAX_TEXT, true)
  },
  servers(message) {
    const entries = message.servers
    if (!Array.isArray(entries) || entries.length > MAX_SERVER_LIST) {
      throw bad(`'servers' is a list of at most ${MAX_SERVER_LIST} servers`)
    }
    for (const entry of entries) checkServerEntry(entry)
  },
}

function checkServerEntry(entry: unknown): void {
  if (!isRecord(entry)) throw bad('a server is an object')
  const origin = entry.origin
  if (!(typeof origin === 'string' && origin.length > 0 && origin.length <= MAX_ADDRESS)) {
    throw bad(`a server's 'origin' is text of 1 to ${MAX_ADDRESS} characters`)
  }
  const label = entry.label
  if (!(typeof label === 'string' && label.length <= MAX_LABEL)) {
    throw bad(`a server's 'label' is text of at most ${MAX_LABEL} characters`)
  }
  if (typeof entry.custom !== 'boolean') throw bad("a server's 'custom' is true or false")
  if ('local' in entry && typeof entry.local !== 'boolean') throw bad("a server's 'local' is true or false")
}

/** The message in `raw` (one JSON object), checked against the contract. Throws `ContractError` (`bad_json` or
 * `bad_message`) for anything the schema refuses and `UnknownMessageType` for a type it does not define. Unknown
 * extra fields are left in place. */
export function parse(raw: string): Message {
  if (new TextEncoder().encode(raw).length > MAX_MESSAGE_BYTES) {
    throw bad(`message too large (more than ${MAX_MESSAGE_BYTES} bytes)`)
  }
  let message: unknown
  try {
    message = JSON.parse(raw)
  } catch (problem) {
    throw new ContractError('bad_json', `not JSON: ${(problem as Error).message}`)
  }
  if (!isRecord(message)) throw bad('a message is a JSON object')
  const kind = message.type
  if (typeof kind !== 'string') throw bad("a message has a 'type'")
  const check = Object.hasOwn(CHECKS, kind) ? CHECKS[kind] : undefined
  if (check === undefined) throw new UnknownMessageType(kind)
  check(message)
  return message as Message
}

/** The version page and shell will speak, or a `ContractError` (`unsupported_contract`). */
export function negotiate(hello: Message, supported: readonly number[] = SUPPORTED_VERSIONS): number {
  const asked = hello.contract as number
  if (supported.includes(asked)) return asked
  throw new ContractError(
    'unsupported_contract',
    `this shell speaks shell contract version ${supported.join(', ')}; the page asked for ${asked}`,
    supported,
  )
}

// ------------------------------------------------------------------------------------------------ building

export interface ShellInfo {
  name: string
  platform: 'linux' | 'windows' | 'macos'
  version: string
}

export function welcome(options: {
  shell: ShellInfo
  capabilities: readonly string[]
  contract?: number
  locale?: string
}): Message {
  const built: Message = {
    type: 'welcome',
    contract: options.contract ?? CONTRACT_VERSION,
    shell: { ...options.shell },
    capabilities: [...options.capabilities],
  }
  if (options.locale !== undefined) built.locale = options.locale
  return built
}

export function action(actionIdValue: string, target?: string): Message {
  const built: Message = { type: 'action', action: actionIdValue }
  if (target !== undefined) built.target = target
  CHECKS.action?.(built)
  return built
}

export function error(code: ErrorCode, message: string, supported?: readonly number[]): Message {
  const built: Message = { type: 'error', code, message: message.slice(0, MAX_TEXT) }
  if (supported !== undefined) built.supported = [...supported]
  CHECKS.error?.(built)
  return built
}

/** The `error` message that answers a `ContractError`. */
export function errorFor(problem: ContractError): Message {
  return error(problem.code, problem.message, problem.supported)
}

export function connectFailed(code: ConnectFailedCode, message: string): Message {
  const built: Message = { type: 'connect_failed', code, message: message.slice(0, MAX_TEXT) }
  CHECKS.connect_failed?.(built)
  return built
}

export type ServerEntry = { origin: string; label: string; custom: boolean; local?: boolean }

export function servers(entries: readonly ServerEntry[]): Message {
  const built: Message = { type: 'servers', servers: entries.map((entry) => ({ ...entry })) }
  CHECKS.servers?.(built)
  return built
}
