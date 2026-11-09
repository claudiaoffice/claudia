#!/usr/bin/env node
// Bundles src/inject-entry.ts into apps/<app>/inject/claudia-bridge.js for every packaged app -- the file
// Neutralino's `modes.window.injectScript` loads into the externally-hosted page (D159 option 2, menu.ts's and
// page-bridge.ts's own top comments explain why). One dependency-free IIFE per app, esbuild's own `define` baking
// in that app's title and generated menu JSON so the bundle needs no fetch or import at page-load time. Identical
// to clients/macos/tools/build-inject.mjs apart from this comment and the one `identity.packaged` cut being
// composes (here) rather than creates (there).
//
// Run via `npm run build:inject` (part of `npm run build`, after `tsc` has produced dist/identity.js, which this
// script reads rather than re-implementing the app table a third time).

import { build } from 'esbuild'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, join } from 'node:path'

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)))

async function main() {
  const identityPath = join(ROOT, 'dist', 'identity.js')
  if (!existsSync(identityPath)) {
    console.error('dist/identity.js is missing -- run `tsc -p tsconfig.json` (or `npm run build`) first')
    process.exitCode = 1
    return
  }
  // A dynamic import() specifier has to be a URL, not a bare filesystem path -- Node accepts an absolute POSIX
  // path as a de facto exception (no "scheme:" prefix to confuse it with), which is exactly why this surfaced
  // only on a real Windows run and not in this package's own Linux-sandbox build: a Windows absolute path IS one,
  // "C:\...", and Node's ESM loader reads "C:" as an unsupported URL scheme (ERR_UNSUPPORTED_ESM_URL_SCHEME)
  // instead of a drive letter. pathToFileURL() is Node's own fix for this, identical on every OS.
  const { APPS, getIdentity } = await import(pathToFileURL(identityPath).href)

  for (const app of APPS) {
    const identity = getIdentity(app)
    if (!identity.packaged) continue // only composes has an apps/<app>/ directory this round (this epic's scope cut)

    const menuPath = join(ROOT, 'src', 'generated', `menu.${app}.json`)
    const menuJson = readFileSync(menuPath, 'utf8')
    const outfile = join(ROOT, 'apps', app, 'inject', 'claudia-bridge.js')

    await build({
      entryPoints: [join(ROOT, 'src', 'inject-entry.ts')],
      bundle: true,
      format: 'iife',
      platform: 'browser',
      target: 'es2020',
      outfile,
      define: {
        __CLAUDIA_APP_TITLE__: JSON.stringify(identity.title),
        __CLAUDIA_MENU_JSON__: JSON.stringify(menuJson),
      },
    })
    console.log(`wrote ${outfile}`)
  }
}

main()
