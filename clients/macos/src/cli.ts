// The command line of the macOS client (E5.11): `claudia-composes`, `claudia-computes`, `claudia-creates`. No
// Neutralino here; the twin of clients/linux/src/claudia_shell_gtk/cli.py.
//
// Every command is the same program for another app:
//
//     claudia-computes                       starts this app's own server on this computer, shows its start page
//     claudia-computes --server HOST[:PORT]  no local server: connects to that one (https; http only for this computer)
//     node dist/launch.js computes           the same, for a checkout that has not been installed
//
// There is no command that asks which app to open: a window is one app, which is also why a window connects only to
// servers of its own app (D242).

import { parseArgs } from 'node:util'
import { APPS, commandOf, getIdentity, isApp, UnknownAppError, type App } from './identity.js'
import { AddressRefused, parseAddress, type Address } from './servers.js'

export interface Options {
  app: App
  /** The server to connect to instead of starting one, or `null` to start the app's own. */
  server: Address | null
  debug: boolean
}

/** What to do with a command line: run, or print something and stop. */
export type Command =
  | { kind: 'run'; options: Options }
  | { kind: 'print'; text: string; code: 0 }
  | { kind: 'usage_error'; text: string; code: 2 }

export function usage(app: App): string {
  const command = commandOf(getIdentity(app))
  return [
    `usage: ${command} [--server URL] [--debug] [--version] [--help]`,
    '',
    `${getIdentity(app).title} for the Mac desktop.`,
    '',
    'options:',
    '  --server URL  connect to this server instead of starting one on this computer',
    '                (https://host[:port]; plain http is only accepted for this computer)',
    '  --debug       print where the logs are',
    '  --version     show the version and exit',
    '  --help        show this help and exit',
  ].join('\n')
}

/** The command that `argv` (without the program name and without the app) asks for. Never throws for bad input:
 * that is a `usage_error`, with the message to print and the exit code (2, as `argparse` does). */
export function parseCommand(app: string, argv: readonly string[], version: string): Command {
  if (!isApp(app)) {
    const problem = new UnknownAppError(app)
    return { kind: 'usage_error', text: `error: ${problem.message}`, code: 2 }
  }
  const command = commandOf(getIdentity(app))
  let values: { server?: string; debug?: boolean; version?: boolean; help?: boolean }
  try {
    values = parseArgs({
      args: [...argv],
      options: {
        server: { type: 'string' },
        debug: { type: 'boolean' },
        version: { type: 'boolean' },
        help: { type: 'boolean', short: 'h' },
      },
      allowPositionals: false,
      strict: true,
    }).values
  } catch (problem) {
    return { kind: 'usage_error', text: `${usage(app).split('\n')[0]}\nerror: ${(problem as Error).message}`, code: 2 }
  }
  if (values.help) return { kind: 'print', text: usage(app), code: 0 }
  if (values.version) return { kind: 'print', text: `${command} ${version}`, code: 0 }
  let server: Address | null = null
  if (values.server !== undefined) {
    try {
      server = parseAddress(values.server)
    } catch (refused) {
      if (!(refused instanceof AddressRefused)) throw refused
      return { kind: 'usage_error', text: `${usage(app).split('\n')[0]}\nerror: argument --server: ${refused.message}`, code: 2 }
    }
  }
  return { kind: 'run', options: { app, server, debug: values.debug === true } }
}

/** `node dist/launch.js APP …`: the app and the arguments after it. Without one it is an error: this client has no
 * picker. */
export function splitAppArgument(argv: readonly string[]): { app: string; rest: string[] } | { error: string } {
  const [first, ...rest] = argv
  if (first === undefined || first.startsWith('-')) {
    return { error: `usage: node dist/launch.js {${APPS.join('|')}} [options]\nerror: say which app to start: ${APPS.join(', ')}` }
  }
  return { app: first, rest }
}
