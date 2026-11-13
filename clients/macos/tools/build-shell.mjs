// Builds what each app's Neutralino window needs, for all three apps (or the ones named on the command line):
//   apps/<app>/index.html       the shell page (from tools/shell-page.template.html)
//   apps/<app>/shell/shell.js   its script: src/shell-page-entry.ts with this app's menu (browser, one file)
//   apps/<app>/ext/core.mjs     the native core: src/core-entry.ts (Node 22, ES module, one file)
// All of it is generated, git-ignored, and rebuilt by `npm run build`.

import { build } from 'esbuild'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const APPS = { composes: 'Claudia Composes', computes: 'Claudia Computes', creates: 'Claudia Creates' }

/** The page, with the app's title in. A function as the replacement: a string would treat `$&` as a pattern. */
export function renderPage(template, title) {
  if (!template.includes('__TITLE__')) throw new Error('the page template has no __TITLE__')
  return template.replaceAll('__TITLE__', () => title)
}

export async function buildApp(app, { quiet = false } = {}) {
  if (!Object.hasOwn(APPS, app)) throw new Error(`unknown app '${app}' (${Object.keys(APPS).join(', ')})`)
  const appDir = join(root, 'apps', app)
  const version = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')).version
  mkdirSync(join(appDir, 'shell'), { recursive: true })
  mkdirSync(join(appDir, 'ext'), { recursive: true })

  writeFileSync(join(appDir, 'index.html'), renderPage(readFileSync(join(root, 'tools', 'shell-page.template.html'), 'utf8'), APPS[app]))

  await build({
    stdin: {
      contents: `import { run } from './shell-page-entry.ts'\nimport listing from './generated/menu.${app}.json'\nrun(${JSON.stringify(app)}, listing, ${JSON.stringify(version)})\n`,
      resolveDir: join(root, 'src'),
      sourcefile: `shell-${app}.ts`,
      loader: 'ts',
    },
    bundle: true,
    format: 'iife',
    platform: 'browser',
    target: 'safari15', // the WKWebView of macOS 12 and newer
    outfile: join(appDir, 'shell', 'shell.js'),
    logLevel: quiet ? 'silent' : 'warning',
  })

  await build({
    entryPoints: [join(root, 'src', 'core-entry.ts')],
    bundle: true,
    format: 'esm',
    platform: 'node',
    target: 'node22',
    outfile: join(appDir, 'ext', 'core.mjs'),
    logLevel: quiet ? 'silent' : 'warning',
  })
  if (!quiet) console.log(`built ${app}`)
}

// Run as a program (not when imported by a test). `pathToFileURL`, not a hand-made `file://` string: the two differ
// for paths with spaces or on Windows (the twin of a fix in clients/windows).
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const wanted = process.argv.slice(2)
  for (const app of wanted.length > 0 ? wanted : Object.keys(APPS)) await buildApp(app)
}
