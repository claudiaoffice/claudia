// The checks a window makes before it shows a server (E5.8, D242): reachable, Claudia, the window's own app, a
// certificate that this computer trusts. Most of it runs against real servers on loopback (plain http, and https
// with a certificate made by openssl for the test); the cases a test cannot make (an expired certificate) use a
// transport that fails the way Node does.
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { createServer as createHttp, type Server as HttpServer } from 'node:http'
import { createServer as createHttps } from 'node:https'
import { createServer as createTcp, type Server as TcpServer, type Socket } from 'node:net'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { HttpTransport, NotHttp, TlsVerifyError, Unreachable, check, type Transport } from '../src/connection.js'
import { parseAddress } from '../src/servers.js'

type Handler = (url: string) => { status: number; body: string }

function claudiaHandler(app: string | null, docsStatus = 200): Handler {
  return (url) => {
    if (url === '/api/health') return { status: 200, body: JSON.stringify({ ok: true }) }
    if (url === '/api/docs') return { status: docsStatus, body: docsStatus === 200 && app ? JSON.stringify({ app }) : '{}' }
    return { status: 404, body: '' }
  }
}

const listening = (server: HttpServer | TcpServer): Promise<number> =>
  new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve((server.address() as { port: number }).port)))
const closing = (server: HttpServer | TcpServer): Promise<void> =>
  new Promise((resolve) => {
    server.close(() => resolve())
    ;(server as HttpServer).closeAllConnections?.()
  })

/** A TCP server (not HTTP) that remembers its connections, so the test can end them. */
function tcpServer(onConnection: (socket: Socket) => void): TcpServer {
  const sockets = new Set<Socket>()
  const server = createTcp((socket) => {
    sockets.add(socket)
    socket.on('close', () => sockets.delete(socket))
    onConnection(socket)
  })
  ;(server as TcpServer & { closeAllConnections: () => void }).closeAllConnections = () => sockets.forEach((s) => s.destroy())
  return server
}

async function http(handler: Handler) {
  const server = createHttp((request, response) => {
    const answer = handler(request.url ?? '/')
    response.writeHead(answer.status, { 'content-type': 'application/json' })
    response.end(answer.body)
  })
  const port = await listening(server)
  return { port, address: parseAddress(`http://127.0.0.1:${port}`), close: () => closing(server) }
}

describe('check against a plain http server on this computer', () => {
  it('reaches a Claudia server of the same app', async () => {
    const server = await http(claudiaHandler('creates'))
    const outcome = await check(server.address, 'creates')
    expect(outcome).toEqual({ kind: 'reached', origin: server.address.origin, app: 'creates' })
    await server.close()
  })

  it("refuses a server of another app, naming both", async () => {
    const server = await http(claudiaHandler('composes'))
    const outcome = await check(server.address, 'creates')
    expect(outcome.kind).toBe('refused')
    if (outcome.kind === 'refused') {
      expect(outcome.code).toBe('wrong_app')
      expect(outcome.message).toContain('Claudia Composes')
      expect(outcome.message).toContain('Claudia Creates')
    }
    await server.close()
  })

  it('reaches a server that keeps its app to itself (a secret is asked first): the page\'s hello decides', async () => {
    for (const status of [401, 403, 404]) {
      const server = await http(claudiaHandler(null, status))
      expect(await check(server.address, 'creates')).toEqual({ kind: 'reached', origin: server.address.origin, app: null })
      await server.close()
    }
  })

  it('refuses a web server that is not Claudia', async () => {
    const server = await http(() => ({ status: 200, body: '<html>hello</html>' }))
    const outcome = await check(server.address, 'creates')
    expect(outcome).toMatchObject({ kind: 'refused', code: 'not_claudia' })
    await server.close()
  })

  it('refuses a health answer that is not {ok: true}, and an app that is not one of ours', async () => {
    const notOk = await http(() => ({ status: 200, body: JSON.stringify({ ok: false }) }))
    expect(await check(notOk.address, 'creates')).toMatchObject({ code: 'not_claudia' })
    await notOk.close()
    const strange = await http(claudiaHandler('spreadsheets'))
    expect(await check(strange.address, 'creates')).toMatchObject({ code: 'not_claudia' })
    await strange.close()
  })

  it('says unreachable when nothing listens', async () => {
    const server = await http(claudiaHandler('creates'))
    const address = server.address
    await server.close()
    expect(await check(address, 'creates')).toMatchObject({ kind: 'refused', code: 'unreachable' })
  })

  it('says not_claudia to something that does not speak HTTP', async () => {
    const tcp = tcpServer((socket) => socket.end('SSH-2.0-OpenSSH_9.0\r\n'))
    const port = await listening(tcp)
    expect(await check(parseAddress(`http://127.0.0.1:${port}`), 'creates')).toMatchObject({ code: 'not_claudia' })
    await closing(tcp)
  })

  it('gives up on a server that does not answer', async () => {
    const tcp = tcpServer(() => {}) // accepts and says nothing
    const port = await listening(tcp)
    const transport = new HttpTransport({ timeoutMs: 150 })
    expect(await check(parseAddress(`http://127.0.0.1:${port}`), 'creates', transport)).toMatchObject({ code: 'unreachable' })
    await closing(tcp)
  })

  it('does not read an answer of any size', async () => {
    const server = await http((url) => (url === '/api/health' ? { status: 200, body: 'x'.repeat(5 * 1024 * 1024) } : { status: 404, body: '' }))
    expect(await check(server.address, 'creates')).toMatchObject({ code: 'not_claudia' })
    await server.close()
  })
})

describe('check refuses what it must not do', () => {
  it('never speaks plain http to another computer', async () => {
    const lan = { scheme: 'http', host: '192.168.1.5', port: 8000, origin: 'http://192.168.1.5:8000', isLoopback: false } as const
    await expect(check(lan, 'creates')).rejects.toThrow(/plain http/)
  })
})

describe('check and the certificate', () => {
  const fake = (problem: Error): Transport => ({
    get: () => Promise.reject(problem),
  })
  const address = parseAddress('demo.example.org')

  it('says expired for an expired certificate', async () => {
    const outcome = await check(address, 'creates', fake(new TlsVerifyError('CERT_HAS_EXPIRED')))
    expect(outcome).toMatchObject({ code: 'certificate_expired' })
    if (outcome.kind === 'refused') expect(outcome.message).toContain('demo.example.org')
  })

  it('says invalid when the issuer is unknown (self-signed, or one this computer does not trust) or the name is wrong', async () => {
    for (const reason of ['DEPTH_ZERO_SELF_SIGNED_CERT', 'UNABLE_TO_VERIFY_LEAF_SIGNATURE', 'ERR_TLS_CERT_ALTNAME_INVALID']) {
      const outcome = await check(address, 'creates', fake(new TlsVerifyError(reason)))
      expect(outcome).toMatchObject({ code: 'certificate_invalid' })
      if (outcome.kind === 'refused') expect(outcome.message).toContain('not issued by an authority this computer trusts')
    }
  })

  it('says invalid, more generally, for any other certificate problem', async () => {
    expect(await check(address, 'creates', fake(new TlsVerifyError('CERT_NOT_YET_VALID')))).toMatchObject({ code: 'certificate_invalid' })
  })

  it('maps the transport errors', async () => {
    expect(await check(address, 'creates', fake(new Unreachable('x')))).toMatchObject({ code: 'unreachable' })
    expect(await check(address, 'creates', fake(new NotHttp('x')))).toMatchObject({ code: 'not_claudia' })
    await expect(check(address, 'creates', fake(new Error('a bug')))).rejects.toThrow('a bug')
  })
})

const hasOpenssl = (() => {
  try {
    execFileSync('openssl', ['version'], { stdio: 'ignore' })
    return true
  } catch {
    return false
  }
})()

describe.skipIf(!hasOpenssl)('check against https with a real certificate', () => {
  let directory: string
  let cert: string
  let key: string
  let otherCert: string
  let server: ReturnType<typeof createHttps>
  let port: number

  const makeCertificate = (name: string, host: string) => {
    const keyFile = join(directory, `${name}.key`)
    const certFile = join(directory, `${name}.crt`)
    execFileSync(
      'openssl',
      ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', keyFile, '-out', certFile, '-days', '2', '-subj', `/CN=${host}`, '-addext', `subjectAltName=DNS:${host}`],
      { stdio: 'ignore' },
    )
    return { key: readFileSync(keyFile, 'utf8'), cert: readFileSync(certFile, 'utf8') }
  }

  beforeAll(async () => {
    directory = mkdtempSync(join(tmpdir(), 'claudia-tls-'))
    ;({ cert, key } = makeCertificate('localhost', 'localhost'))
    otherCert = makeCertificate('other', 'other.example').cert
    server = createHttps({ key, cert }, (request, response) => {
      const answer = claudiaHandler('creates')(request.url ?? '/')
      response.writeHead(answer.status, { 'content-type': 'application/json' })
      response.end(answer.body)
    })
    port = await listening(server as unknown as HttpServer)
  })
  afterAll(async () => {
    await closing(server as unknown as HttpServer)
    rmSync(directory, { recursive: true, force: true })
  })

  it("refuses a certificate that nobody this computer trusts vouches for (D245's pin is not built yet)", async () => {
    const outcome = await check(parseAddress(`https://localhost:${port}`), 'creates')
    expect(outcome).toMatchObject({ kind: 'refused', code: 'certificate_invalid' })
  })

  it('reaches the server when the certificate is trusted', async () => {
    const outcome = await check(parseAddress(`https://localhost:${port}`), 'creates', new HttpTransport({ ca: cert }))
    expect(outcome).toEqual({ kind: 'reached', origin: `https://localhost:${port}`, app: 'creates' })
  })

  it('refuses a trusted certificate that is for another name', async () => {
    const outcome = await check(parseAddress(`https://localhost:${port}`), 'creates', new HttpTransport({ ca: otherCert }))
    expect(outcome).toMatchObject({ code: 'certificate_invalid' })
  })
})
