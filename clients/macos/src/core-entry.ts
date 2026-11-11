// The program Neutralino starts as the window's extension (`apps/<app>/ext/core.mjs`, bundled by tools/build-shell.mjs,
// started with the command that core-command.ts builds): it reads the tokens Neutralino sends on stdin, links to
// Neutralino (extension.ts), and runs the `Core` of its app. It ends when the window is gone, after stopping what
// it started.
//
// Nobody sees this process's console, and a window that waits for a core that is not there only says "Starting…".
// So everything this program does, and every way it can fail, is written to a log file from its first line on:
// `<state dir of the app>/shell.log`, or `shell.log` in the suite's folder when it does not even know its app.

import { Core } from './core.js'
import { parseCoreArgs } from './core-command.js'
import { FROM_CORE, isRequest, TO_CORE } from './core-protocol.js'
import { describeAuthInput, ExtensionLink, parseAuth } from './extension.js'
import { appFromPath, getIdentity } from './identity.js'
import { configDir, stateDir } from './paths.js'
import { parseAddress } from './servers.js'
import { Settings } from './settings.js'
import { appendFileSync, fstatSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

type Log = (message: string) => void

function logTo(file: string): Log {
  return (message) => {
    try {
      mkdirSync(dirname(file), { recursive: true })
      appendFileSync(file, `${new Date().toISOString()} [core ${process.pid}] ${message}\n`)
    } catch {
      // a log that cannot be written is not a reason to stop
    }
  }
}

/** Which app this core is for: what its command line says, else the environment, else what its own place says
 * (`apps/<app>/ext/`). */
function findApp(args: { app: string | null }): string {
  return args.app || process.env.CLAUDIA_SHELL_APP || appFromPath(fileURLToPath(import.meta.url)) || ''
}

/** What file descriptor 0 is (a pipe, a file, a terminal, /dev/null...): the first thing to look at when the tokens do not come. */
function describeStdin(): string {
  try {
    const stat = fstatSync(0)
    if (stat.isFIFO()) return 'a pipe'
    if (stat.isSocket()) return 'a socket'
    if (stat.isCharacterDevice()) return 'a character device (terminal or /dev/null)'
    return stat.isFile() ? 'a file' : 'something else'
  } catch (problem) {
    return `not readable (${(problem as Error).message})`
  }
}

function main(): void {
  // Until the app is known the log is the suite's; then it is the app's own.
  let log: Log = logTo(join(configDir(), 'shell.log'))
  const args = parseCoreArgs(process.argv.slice(2))
  log(`started: node ${process.version}, ${process.execPath}; arguments ${JSON.stringify(process.argv.slice(2))}; stdin is ${describeStdin()}`)
  const fatal = (what: string) => (problem: unknown) => {
    log(`${what}: ${(problem as Error)?.stack ?? problem}`)
    process.exit(1)
  }
  process.on('uncaughtException', fatal('uncaught exception'))
  process.on('unhandledRejection', fatal('unhandled rejection'))

  if (typeof WebSocket === 'undefined') {
    log(`this Node (${process.version}) has no WebSocket; the core needs Node 22 or newer`)
    process.exit(1)
  }
  const identity = getIdentity(findApp(args)) // throws a clear message for a wrong environment, which the log gets above
  const appLog = logTo(join(stateDir(identity.name), 'shell.log'))
  log = appLog
  const server = args.server ?? (process.env.CLAUDIA_SHELL_SERVER || null)
  appLog(`app ${identity.name}, server ${server ?? '(its own)'}, NODE_OPTIONS ${process.env.NODE_OPTIONS ?? '(none)'}`)
  const given = server ? parseAddress(server) : null

  let raw = ''
  let started = false
  process.stdin.setEncoding('utf8')
  process.stdin.on('data', (chunk: string) => {
    raw += chunk
    if (started) return
    const auth = parseAuth(raw)
    if (auth === null) {
      // not complete yet, or not what was expected: the log says which (it is how a mismatch with Neutralino is found)
      appLog(`stdin: ${describeAuthInput(raw)}; not usable (yet)`)
      return
    }
    started = true
    appLog(`got the tokens from Neutralino (port ${auth.nlPort}, extension ${auth.nlExtensionId}); connecting`)
    let link: ExtensionLink | null = null
    const core = new Core({
      identity,
      settings: new Settings(undefined, appLog),
      given,
      log: appLog,
      send: (message) => {
        appLog(`-> page: ${message.kind}`)
        link?.broadcast(FROM_CORE, message)
      },
    })
    link = new ExtensionLink(auth, {
      onEvent: (event, data) => {
        if (event !== TO_CORE) return
        if (isRequest(data)) {
          appLog(`<- page: ${data.kind}`)
          core.handle(data)
        } else appLog('ignored a request of the shell page that is not one')
      },
      onOpen: () => appLog('connected to Neutralino'),
      onClosed: () => {
        appLog('the link to Neutralino is closed; ending')
        void core.stop().finally(() => process.exit(0))
      },
      log: appLog,
    })
  })
  process.stdin.on('end', () => {
    if (!started) appLog(`stdin ended before the tokens arrived (it had delivered ${raw.length} characters)`)
  })
}

try {
  main()
} catch (problem) {
  logTo(join(configDir(), 'shell.log'))(`could not start: ${(problem as Error)?.stack ?? problem}`)
  process.exit(1)
}
