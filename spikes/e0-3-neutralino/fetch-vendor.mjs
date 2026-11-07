// Fetches the pinned plotly.js build into page/vendor/ (the patch does not carry its 4.5 MB). Needs Node and network.
// Run by the wrappers in neutralino/; safe to run again, it does nothing when the file is there.
import { execSync } from 'node:child_process'
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const PLOTLY = 'plotly.js-dist-min@3.7.0'
const root = dirname(fileURLToPath(import.meta.url))
const vendor = join(root, 'page', 'vendor')
const cache = join(root, '.cache')

if (existsSync(join(vendor, 'plotly.min.js'))) process.exit(0)

console.log(`Fetching ${PLOTLY} ...`)
mkdirSync(vendor, { recursive: true })
execSync(`npm install --no-save --no-package-lock --no-audit --no-fund --prefix "${cache}" ${PLOTLY}`, { stdio: 'inherit' })
const pkg = join(cache, 'node_modules', 'plotly.js-dist-min')
copyFileSync(join(pkg, 'plotly.min.js'), join(vendor, 'plotly.min.js'))
copyFileSync(join(pkg, 'LICENSE'), join(vendor, 'plotly.LICENSE'))
