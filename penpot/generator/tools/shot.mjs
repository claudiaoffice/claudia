import { chromium } from 'playwright-core'
const [url, out, w, h, dark] = process.argv.slice(2)
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome', args: ['--no-sandbox'] })
const p = await b.newPage({ viewport: { width: +w, height: +h } })
await p.goto(url)
if (dark) await p.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
await p.waitForTimeout(1500)
await p.screenshot({ path: out })
await b.close()
