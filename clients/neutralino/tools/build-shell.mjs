// Builds what each app's Neutralino window needs, for all three apps (or the ones named on the command line), for one
// platform (D660): `--platform macos` or `--platform windows`, else the one this runs on (Windows, or else macOS):
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
/** What each platform's web view understands: the WKWebView of macOS 12 and newer; WebView2, which is Chromium and
 * updates itself (109 is what Windows 10 and 11 can still run). */
export const TARGETS = { macos: 'safari15', windows: 'chrome109' }

/** The platform a build is for: `--platform NAME` among the arguments, else the one this runs on. */
export function platformOf(args, nodePlatform = process.platform) {
  const at = args.indexOf('--platform')
  const named = at >= 0 ? args[at + 1] : nodePlatform === 'win32' ? 'windows' : 'macos'
  if (!Object.hasOwn(TARGETS, named)) throw new Error(`unknown platform '${named}' (${Object.keys(TARGETS).join(', ')})`)
  return named
}

/** The apps named among the arguments (all three when none is), without the `--platform` option. */
export function appsOf(args) {
  const at = args.indexOf('--platform')
  const wanted = args.filter((_, i) => at < 0 || (i !== at && i !== at + 1))
  return wanted.length > 0 ? wanted : Object.keys(APPS)
}

/** The page, with the app's title in. A function as the replacement: a string would treat `$&` as a pattern. */
export function renderPage(template, title) {
  if (!template.includes('__TITLE__')) throw new Error('the page template has no __TITLE__')
  return template.replaceAll('__TITLE__', () => title)
}

/** Builds one app for one platform into `apps/<app>/`, or into `into` (a test builds the other platform elsewhere, so
 * that it never meets a build of this one). */
export async function buildApp(app, { quiet = false, platform = platformOf([]), into } = {}) {
  if (!Object.hasOwn(TARGETS, platform)) throw new Error(`unknown platform '${platform}' (${Object.keys(TARGETS).join(', ')})`)
  // The bundles know their platform (src/platform/id.ts); a Windows build behaves like Windows wherever it runs.
  const define = { CLAUDIA_PLATFORM: JSON.stringify(platform) }
  if (!Object.hasOwn(APPS, app)) throw new Error(`unknown app '${app}' (${Object.keys(APPS).join(', ')})`)
  const appDir = into ?? join(root, 'apps', app)
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
    target: TARGETS[platform],
    define,
    outfile: join(appDir, 'shell', 'shell.js'),
    logLevel: quiet ? 'silent' : 'warning',
  })

  await build({
    entryPoints: [join(root, 'src', 'core-entry.ts')],
    bundle: true,
    format: 'esm',
    platform: 'node',
    target: 'node22',
    define,
    outfile: join(appDir, 'ext', 'core.mjs'),
    logLevel: quiet ? 'silent' : 'warning',
  })
  if (!quiet) console.log(`built ${app} for ${platform}`)
}

// Run as a program (not when imported by a test). `pathToFileURL`, not a hand-made `file://` string: the two differ
// for paths with spaces or on Windows (notes/e5-11-windows-client.md).
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const args = process.argv.slice(2)
  const platform = platformOf(args)
  for (const app of appsOf(args)) await buildApp(app, { platform })
}
