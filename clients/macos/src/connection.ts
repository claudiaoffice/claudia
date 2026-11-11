// Can this window connect to the server at an address? (E5.8) Port of clients/linux/src/claudia_shell_gtk/
// connection.py: the second and third step of the order the mock-up shows (`notes/mockups/connect-and-trust.svg`,
// panel D; step 1, the address itself, is `servers.parseAddress`):
//
//  - **reach it, check the certificate** -- the server answers `/api/health` over TLS. A certificate that this
//    computer trusts needs no question. One that nobody vouches for (self-signed, an authority this computer does
//    not know, a name that is not the server's) would be *offered to the person*; that question is not built for
//    any desktop client yet, so it is refused with `certificate_invalid`, the same thing the Linux client does when
//    it has no dialog (`Connector.ask_trust` unset). An expired or not yet valid certificate is refused with its
//    own code;
//  - **same app** -- `/api/docs` names the app the server runs, and it must be the app of this window. A server
//    that keeps its document list behind a secret does not say; the page's own `hello`, which names the app, is
//    checked again when the page loads (shell-page.ts).
//
// Whether the server is a Claudia server and runs the right app is decided before anything else is said about its
// certificate: nobody should be told about a certificate of a server she could not use anyway.
//
// The network is behind `Transport` (Node's `http`/`https`), so everything else is tested with real local servers
// or with a fake. Node validates against its own bundled authorities unless started with `--use-system-ca`, which
// the launcher sets when this Node supports it (launch.ts), so a certificate that macOS trusts (a company
// authority in the keychain, say) is trusted here too.

import http from 'node:http'
import https from 'node:https'
import { isApp, getIdentity } from './identity.js'
import { defaultLabel, type Address } from './servers.js'

export const HEALTH_PATH = '/api/health'
export const DOCS_PATH = '/api/docs'
/** Bytes read of one answer at most. A server of another kind must not be able to fill the memory. */
export const MAX_BODY = 4 * 1024 * 1024
export const TIMEOUT_MS = 8000

export interface Response {
  status: number
  body: Buffer
}

/** The answers to a list of paths. */
export type Fetched = Record<string, Response>

/** The system refused the certificate; `reason` names why (OpenSSL's `X509_V_ERR` name, as Node reports it). */
export class TlsVerifyError extends Error {
  constructor(readonly reason: string) {
    super(`certificate verification failed (${reason})`)
    this.name = 'TlsVerifyError'
  }
}

/** Nobody answered: refused, unknown host, no route, timed out. */
export class Unreachable extends Error {}

/** Somebody answered, but not with HTTP (or not within `MAX_BODY`). */
export class NotHttp extends Error {}

export interface Transport {
  /** GET `paths` over one connection (verified TLS for https). */
  get(address: Address, paths: readonly string[]): Promise<Fetched>
}

const EXPIRED = new Set(['CERT_HAS_EXPIRED'])
const NOT_YET_VALID = new Set(['CERT_NOT_YET_VALID'])
const UNKNOWN_ISSUER = new Set([
  'DEPTH_ZERO_SELF_SIGNED_CERT',
  'SELF_SIGNED_CERT_IN_CHAIN',
  'UNABLE_TO_GET_ISSUER_CERT',
  'UNABLE_TO_GET_ISSUER_CERT_LOCALLY',
  'UNABLE_TO_VERIFY_LEAF_SIGNATURE',
  'CERT_UNTRUSTED',
])
const NAME_MISMATCH = new Set(['ERR_TLS_CERT_ALTNAME_INVALID', 'HOSTNAME_MISMATCH'])
const NETWORK = new Set([
  'ECONNREFUSED',
  'ENOTFOUND',
  'EHOSTUNREACH',
  'ENETUNREACH',
  'ETIMEDOUT',
  'ECONNRESET',
  'EAI_AGAIN',
  'EPIPE',
  'ECONNABORTED',
])

function readBody(response: http.IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = []
    let size = 0
    response.on('data', (chunk: Buffer) => {
      size += chunk.length
      if (size > MAX_BODY) {
        response.destroy()
        reject(new NotHttp('answer too large'))
        return
      }
      chunks.push(chunk)
    })
    response.on('end', () => resolve(Buffer.concat(chunks)))
    response.on('error', (problem) => reject(new NotHttp(problem.message)))
    response.on('aborted', () => reject(new NotHttp('answer cut off')))
  })
}

/** The real transport. `ca` replaces the system's authorities (tests); `timeoutMs` is per request. */
export class HttpTransport implements Transport {
  constructor(private readonly options: { ca?: string | Buffer; timeoutMs?: number } = {}) {}

  async get(address: Address, paths: readonly string[]): Promise<Fetched> {
    const answers: Fetched = {}
    const tls = address.scheme === 'https'
    const agent = tls
      ? new https.Agent({ keepAlive: true, maxSockets: 1, ...(this.options.ca ? { ca: this.options.ca } : {}) })
      : new http.Agent({ keepAlive: true, maxSockets: 1 })
    try {
      for (const path of paths) answers[path] = await this.one(address, path, agent, tls)
    } finally {
      agent.destroy()
    }
    return answers
  }

  private one(address: Address, path: string, agent: http.Agent, tls: boolean): Promise<Response> {
    return new Promise((resolve, reject) => {
      const timeout = this.options.timeoutMs ?? TIMEOUT_MS
      const request = (tls ? https : http).request(
        {
          host: address.host,
          port: address.port ?? (tls ? 443 : 80),
          path,
          method: 'GET',
          agent,
          timeout,
          headers: { Accept: 'application/json', 'User-Agent': 'claudia-shell' },
        },
        (response) => {
          readBody(response).then((body) => resolve({ status: response.statusCode ?? 0, body }), reject)
        },
      )
      request.on('timeout', () => request.destroy(Object.assign(new Error('timed out'), { code: 'ETIMEDOUT' })))
      request.on('error', (problem: NodeJS.ErrnoException) => {
        const code = problem.code ?? ''
        if (EXPIRED.has(code) || NOT_YET_VALID.has(code) || UNKNOWN_ISSUER.has(code) || NAME_MISMATCH.has(code)) {
          reject(new TlsVerifyError(code))
        } else if (NETWORK.has(code)) {
          reject(new Unreachable(problem.message))
        } else if (code.startsWith('ERR_SSL') || code.startsWith('ERR_TLS') || code.startsWith('ERR_OSSL')) {
          reject(new NotHttp(problem.message)) // somebody answered, but not with TLS as we know it
        } else if (code.startsWith('HPE_') || code === 'ERR_HTTP_REQUEST_TIMEOUT') {
          reject(new NotHttp(problem.message))
        } else {
          reject(new Unreachable(problem.message))
        }
      })
      request.end()
    })
  }
}

// -------------------------------------------------------------------------------------------------- outcomes

/** The server answers, is a Claudia server, and (when it said) runs this window's app. */
export interface Reached {
  kind: 'reached'
  origin: string
  /** The app the server named, or `null` when it did not say (the hello check remains). */
  app: string | null
}

/** A stop. `code` is one of `contract.CONNECT_FAILED_CODES`; `message` is written for the person. */
export interface Refused {
  kind: 'refused'
  code:
    | 'unreachable'
    | 'not_claudia'
    | 'wrong_app'
    | 'certificate_expired'
    | 'certificate_invalid'
    | 'bad_address'
    | 'insecure'
    | 'not_trusted'
  message: string
}

export type Outcome = Reached | Refused

const refused = (code: Refused['code'], message: string): Refused => ({ kind: 'refused', code, message })
const notClaudia = (): Refused => refused('not_claudia', 'That does not look like a Claudia server.')

function json(response: Response): unknown {
  try {
    return JSON.parse(response.body.toString('utf8'))
  } catch {
    return null
  }
}

/** Is this a Claudia server of `expectedApp`? A refusal, or the app it named (`null` if it did not say). */
function interpret(fetched: Fetched, expectedApp: string): Refused | { app: string | null } {
  const health = fetched[HEALTH_PATH]
  const body = health !== undefined && health.status === 200 ? json(health) : null
  if (!(typeof body === 'object' && body !== null && (body as Record<string, unknown>).ok === true)) return notClaudia()
  const docs = fetched[DOCS_PATH]
  if (docs === undefined || [401, 403, 404].includes(docs.status)) return { app: null }
  const listing = docs.status === 200 ? json(docs) : null
  const app = typeof listing === 'object' && listing !== null ? (listing as Record<string, unknown>).app : undefined
  if (typeof app !== 'string' || !isApp(app)) return notClaudia()
  if (app !== expectedApp) {
    return refused(
      'wrong_app',
      `That server runs ${getIdentity(app).title}. This window is ${getIdentity(expectedApp).title} — open it there.`,
    )
  }
  return { app }
}

function certificateRefusal(reason: string, host: string): Refused {
  if (EXPIRED.has(reason)) {
    return refused('certificate_expired', `The certificate of ${host} has expired. Ask its administrator to renew it.`)
  }
  if (UNKNOWN_ISSUER.has(reason) || NAME_MISMATCH.has(reason)) {
    return refused('certificate_invalid', `The certificate of ${host} is not issued by an authority this computer trusts.`)
  }
  return refused('certificate_invalid', `The certificate of ${host} is not valid.`)
}

/** What happens when this window (of `expectedApp`) connects to `address` -- see the top of this file. Takes up to a
 * few seconds; never awaited on the shell page's own thread. */
export async function check(address: Address, expectedApp: string, transport: Transport = new HttpTransport()): Promise<Outcome> {
  if (address.scheme === 'http' && !address.isLoopback) throw new Error('plain http is only for a loopback address')
  try {
    const fetched = await transport.get(address, [HEALTH_PATH, DOCS_PATH])
    const verdict = interpret(fetched, expectedApp)
    return 'kind' in verdict ? verdict : { kind: 'reached', origin: address.origin, app: verdict.app }
  } catch (problem) {
    if (problem instanceof TlsVerifyError) return certificateRefusal(problem.reason, address.host)
    if (problem instanceof Unreachable) return refused('unreachable', `Could not reach ${defaultLabel(address.origin)}.`)
    if (problem instanceof NotHttp) return notClaudia()
    throw problem
  }
}
