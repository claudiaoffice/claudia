// How the core is started: the command in neutralino.config.json (`extensions[].commandDarwin`) and the arguments
// the core reads from it. Everything the core needs travels in that one command line -- the absolute path of node,
// the certificate option, the app, the server -- because nothing else is known to reach an extension: the settings
// were first environment variables (Neutralino is not documented to pass its environment on), and then a wrapper
// script, which Neutralino started but gave no tokens on stdin (the core logged "stdin ended before the tokens
// arrived", first run on a real Mac, 2026-11-11). What spike 5 proved on a Mac is a direct command with the absolute
// path of node, so this keeps to exactly that shape.
//
// The launcher puts the command into the app's config before it starts the window and puts the default back when the
// window has ended, so a checkout is left as it was found.

import { readFileSync, writeFileSync } from 'node:fs'
import { CORE_ID } from './core-protocol.js'

/** What the checked-in config holds: runs when someone starts Neutralino without the launcher (the core then knows its
 * app from its folder and starts its own server). */
export const DEFAULT_COMMAND = 'node ${NL_PATH}/ext/core.mjs'

export interface CoreCommandOptions {
  nodeBinary: string
  systemCa: boolean
  app: string
  server: string | null
  debug: boolean
}

/** The command. Neutralino splits it at spaces and knows no quoting, so a part with whitespace in it cannot be passed. */
export function buildCoreCommand(options: CoreCommandOptions): string {
  const parts = [
    options.nodeBinary,
    ...(options.systemCa ? ['--use-system-ca'] : []),
    '${NL_PATH}/ext/core.mjs',
    `--app=${options.app}`,
    ...(options.server !== null ? [`--server=${options.server}`] : []),
    ...(options.debug ? ['--debug'] : []),
  ]
  const bad = parts.find((part) => /\s/.test(part))
  if (bad !== undefined) {
    throw new Error(`'${bad}' has a space in it, and Neutralino cannot pass that to the core (install node in a path without spaces)`)
  }
  return parts.join(' ')
}

export interface CoreArgs {
  app: string | null
  server: string | null
  debug: boolean
}

/** What the core was given on its command line (`process.argv.slice(2)`); unknown arguments are ignored. */
export function parseCoreArgs(argv: readonly string[]): CoreArgs {
  const found: CoreArgs = { app: null, server: null, debug: false }
  for (const argument of argv) {
    if (argument.startsWith('--app=')) found.app = argument.slice('--app='.length) || null
    else if (argument.startsWith('--server=')) found.server = argument.slice('--server='.length) || null
    else if (argument === '--debug') found.debug = true
  }
  return found
}

/** Sets the core's command in the config file, in the file's own format (two spaces, final newline). */
export function setCoreCommand(configFile: string, command: string): void {
  const config = JSON.parse(readFileSync(configFile, 'utf8')) as { extensions?: Array<{ id: string; commandDarwin?: string }> }
  const entry = config.extensions?.find((extension) => extension.id === CORE_ID)
  if (entry === undefined) throw new Error(`${configFile} has no extension '${CORE_ID}'`)
  entry.commandDarwin = command
  writeFileSync(configFile, JSON.stringify(config, null, 2) + '\n')
}
