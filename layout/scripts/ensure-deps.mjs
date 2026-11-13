#!/usr/bin/env node
// Make sure the layout library's own dependencies are installed in layout/node_modules.
//
// An app links the library (`"@claudia/layout": "file:../layout"`), and npm installs only a symlink for that: the
// library's dependencies (HarfBuzz, fflate, linebreak) are resolved from the library's folder, where nobody installed
// them. The web app runs this script after its own `npm ci`/`npm install` (`postinstall`), so a fresh checkout
// builds with one install.
//
// It does nothing when every package of layout/package-lock.json is already installed at its locked version.
// Otherwise it runs `npm ci` in layout/: without the development tools, unless they were there before (someone
// works on the library itself and keeps its tests runnable).
//
// Usage: node node_modules/@claudia/layout/scripts/ensure-deps.mjs
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const lock = JSON.parse(readFileSync(join(root, 'package-lock.json'), 'utf8'))
const withDev = existsSync(join(root, 'node_modules', 'vitest', 'package.json'))

function installedVersion(path) {
  try {
    return JSON.parse(readFileSync(join(root, path, 'package.json'), 'utf8')).version
  } catch {
    return undefined
  }
}

const stale = Object.entries(lock.packages ?? {})
  // optional packages are often for another platform (a native binary per OS) and are rightly not installed
  .filter(([path, info]) => path.startsWith('node_modules/') && !info.link && !info.optional && (withDev || !info.dev))
  .filter(([path, info]) => installedVersion(path) !== info.version)
  .map(([path]) => path.slice('node_modules/'.length))

if (stale.length === 0) {
  console.log('@claudia/layout: its dependencies are installed')
  process.exit(0)
}

const args = ['ci', '--no-audit', '--no-fund', ...(withDev ? [] : ['--omit=dev'])]
console.log(`@claudia/layout: installing its dependencies (npm ${args.join(' ')}; missing or out of date: ${stale.slice(0, 5).join(', ')}${stale.length > 5 ? ', …' : ''})`)
// The npm that runs this script, so that it works the same on Windows (no npm.cmd shell lookup) and under nvm.
const npm = process.env.npm_execpath
const result = npm
  ? spawnSync(process.execPath, [npm, ...args], { cwd: root, stdio: 'inherit' })
  : spawnSync('npm', args, { cwd: root, stdio: 'inherit', shell: process.platform === 'win32' })
if (result.status !== 0) {
  console.error(`@claudia/layout: npm ci in ${root} failed`)
  process.exit(result.status ?? 1)
}
