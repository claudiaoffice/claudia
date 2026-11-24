// How the core is started: the command in neutralino.config.json (`extensions[].commandDarwin` on a Mac,
// `commandWindows` on Windows; the checked-in config holds both, src/platform/host.ts says which) and the arguments
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
 * app from its folder and uses the local server of the suite). */
export const DEFAULT_COMMAND = 'node ${NL_PATH}/ext/core.mjs'

/** The key of the core's command in the config: Neutralino reads one per operating system. */
export type CoreCommandKey = 'commandDarwin' | 'commandWindows'

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

/** Writes the config the way the file was: two spaces, a final newline, and the line ends it had (a checkout on Windows
 * may have CRLF, and a rewrite that turned them into LF would show as a change of every line). */
function writeConfig(configFile: string, original: string, config: unknown): void {
  const eol = original.includes('\r\n') ? '\r\n' : '\n'
  writeFileSync(configFile, JSON.stringify(config, null, 2).replace(/\n/g, eol) + eol)
}

/** Switches the web inspector of the window on or off in the config file. Neutralino opens the inspector (the
 * DevTools window) by itself at start when it is on, so the checked-in config has it off and only `--debug` turns it
 * on, for that run. */
export function setInspector(configFile: string, enabled: boolean): void {
  const text = readFileSync(configFile, 'utf8')
  const config = JSON.parse(text) as { modes?: { window?: { enableInspector?: boolean } } }
  const window = config.modes?.window
  if (window === undefined) throw new Error(`${configFile} has no modes.window`)
  window.enableInspector = enabled
  writeConfig(configFile, text, config)
}

/** Has Neutralino take the window's size in logical pixels, which it multiplies by the display scale (UX-77, D749); off
 * takes the key out again, so the config is as it was found. */
export function setLogicalPixels(configFile: string, enabled: boolean): void {
  const text = readFileSync(configFile, 'utf8')
  const config = JSON.parse(text) as { modes?: { window?: { useLogicalPixels?: boolean } } }
  const window = config.modes?.window
  if (window === undefined) throw new Error(`${configFile} has no modes.window`)
  if (enabled) window.useLogicalPixels = true
  else delete window.useLogicalPixels
  writeConfig(configFile, text, config)
}

/** Sets the core's command for one operating system (`key`) in the config file, in the file's own format (two spaces,
 * final newline, its line ends). */
export function setCoreCommand(configFile: string, command: string, key: CoreCommandKey): void {
  const text = readFileSync(configFile, 'utf8')
  const config = JSON.parse(text) as { extensions?: Array<{ id: string } & Partial<Record<CoreCommandKey, string>>> }
  const entry = config.extensions?.find((extension) => extension.id === CORE_ID)
  if (entry === undefined) throw new Error(`${configFile} has no extension '${CORE_ID}'`)
  entry[key] = command
  writeConfig(configFile, text, config)
}
