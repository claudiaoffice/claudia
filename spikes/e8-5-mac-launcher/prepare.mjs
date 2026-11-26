// Spike E8.5 (throwaway): what `launch.ts --prepare` will do for an installed macOS app, written against the client's
// built modules so that the spike runs the real core, page and server.
//
//   node prepare.mjs <app> <runtime folder> <neutralino binary>
//
// 1. copies <runtime>/client/apps/<app> to ~/Library/Caches/Claudia/run/<app> (no space in that path),
// 2. links `node` in there to the bundled node (its own path has a space: "Application Support"),
// 3. writes the core's command (naming that link) into the copy's neutralino.config.json,
// 4. writes window.sh: the window's environment and `exec <neutralino> --path=<copy> --res-mode=directory`, each value
//    quoted, so that the app's launcher can `exec` it and the process macOS launched becomes the window.
// The server is the checkout's (.venv): settings.sh beside this file names it (the real package has its own server).

import { mkdirSync, readFileSync, symlinkSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'
import { pathToFileURL } from 'node:url'

export function shellQuote(value) {
  return `'${String(value).replaceAll("'", `'\\''`)}'`
}

export function windowScript(environment, command) {
  const lines = ['#!/bin/sh', '# Written by prepare.mjs (spike E8.5) at every start; not to be edited.']
  for (const [name, value] of Object.entries(environment).sort(([a], [b]) => a.localeCompare(b))) {
    if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) lines.push(`export ${name}=${shellQuote(value)}`)
  }
  lines.push(`exec ${command.map(shellQuote).join(' ')}`)
  return lines.join('\n') + '\n'
}

function settings(file) {
  const found = {}
  for (const line of readFileSync(file, 'utf8').split('\n')) {
    const match = /^([A-Z_]+)=(.*)$/.exec(line.trim())
    if (match) found[match[1]] = match[2].replace(/^'(.*)'$/, '$1')
  }
  return found
}

export async function prepare(app, runtime, neutralino, { home = homedir(), env = process.env } = {}) {
  const client = join(runtime, 'client')
  const load = (name) => import(pathToFileURL(join(client, 'dist', name)).href)
  const { stageApp } = await load('packaged.js')
  const { buildCoreCommand, setCoreCommand } = await load('core-command.js')
  const { buildShellEnvironment, buildShellCommand } = await load('launch.js')

  const appDir = join(client, 'apps', app)
  const runDir = join(home, 'Library', 'Caches', 'Claudia', 'run', app)
  if (/\s/.test(runDir)) throw new Error(`the run folder has a space in it: ${runDir}`)
  mkdirSync(dirname(runDir), { recursive: true })
  stageApp(appDir, runDir)

  const node = join(runtime, 'node', 'bin', 'node')
  const nodeLink = join(runDir, 'node')
  symlinkSync(node, nodeLink)
  setCoreCommand(
    join(runDir, 'neutralino.config.json'),
    buildCoreCommand({ nodeBinary: nodeLink, systemCa: true, app, server: null, debug: false }),
    'commandDarwin',
  )

  const environment = buildShellEnvironment({ app, server: null, debug: false }, env, node, true)
  const own = settings(join(runtime, 'spike', 'settings.sh'))
  environment.CLAUDIA_WEB_DIR = join(runtime, 'web')
  environment.CLAUDIA_SERVER_PYTHON = own.CLAUDIA_SERVER_PYTHON
  const script = join(runDir, 'window.sh')
  writeFileSync(script, windowScript(environment, buildShellCommand(neutralino, runDir)), { mode: 0o700 })
  return script
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [app, runtime, neutralino] = process.argv.slice(2)
  if (!app || !runtime || !neutralino) {
    console.error('usage: node prepare.mjs <app> <runtime folder> <neutralino binary>')
    process.exit(2)
  }
  try {
    console.log(`prepared ${await prepare(app, runtime, neutralino)}`)
  } catch (problem) {
    console.error(`prepare failed: ${problem.message}`)
    process.exit(1)
  }
}

