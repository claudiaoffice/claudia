// What happens when things go wrong: a viewer tries to edit, and the server restarts under people's hands.
const { chromium } = require('playwright')
const { spawn } = require('node:child_process')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '../..')
const PORT = 8766
const URL = `http://127.0.0.1:${PORT}/`
const DATA = fs.mkdtempSync(path.join(os.tmpdir(), 'claudia-e2e-'))
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function startServer() {
  const child = spawn(
    path.join(ROOT, '.venv/bin/python'),
    ['-m', 'claudia_server', '--no-tls', '--port', String(PORT), '--dir', DATA, '--web', path.join(ROOT, 'web/.output/public')],
    { cwd: ROOT, stdio: process.env.SERVER_LOG ? ['ignore', fs.openSync(process.env.SERVER_LOG, 'a'), fs.openSync(process.env.SERVER_LOG, 'a')] : 'ignore' },
  )
  return child
}
async function ready() {
  for (let i = 0; i < 50; i++) {
    try {
      if ((await fetch(URL + 'api/health')).ok) return
    } catch {}
    await sleep(200)
  }
  throw new Error('the server did not start')
}
async function login(browser, doc, user, password, create) {
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 800 } })).newPage()
  page.errors = []
  page.on('pageerror', (e) => page.errors.push(e.message))
  await page.goto(URL)
  await page.fill('input[name=document]', doc)
  await page.fill('input[name=user]', user)
  await page.fill('input[name=password]', password)
  await page.click(create ? 'text=Create document' : 'button:text-is("Open")')
  if (create) {
    // a new document first shows its recovery key; the person must confirm having stored it
    await page.waitForSelector('[data-testid=recovery-key]')
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
  }
  await page.waitForSelector('.viewport')
  await page.waitForFunction(() => document.querySelector('.health.open'))
  return page
}
const wait = (page, fn, arg, what) => page.waitForFunction(fn, arg, { timeout: 15000 }).catch(() => Promise.reject(new Error('timed out: ' + what)))

;(async () => {
  let server = startServer()
  const browser = await chromium.launch()
  try {
    await ready()
    const ann = await login(browser, 'plan', 'ann', 'Ann-has-a-Password-1', true)
    await ann.click('.viewport', { position: { x: 100, y: 40 } })
    await ann.keyboard.type('hello')
    await ann.keyboard.press('Enter')
    await wait(ann, () => document.querySelector('.cell'), null, 'first cell')

    // a formula is calculated (the toast that once said formulas were not there yet is long gone)
    await ann.keyboard.type('=1+1')
    await ann.keyboard.press('Enter')
    await wait(ann, () => [...document.querySelectorAll('.cell')].some((c) => c.textContent.trim() === '2'), null, 'formula result')
    console.log('formula calculated: =1+1 shows 2')

    // ---- a viewer may look and not touch
    await ann.click('.menus .title:text-is("File")')
    await ann.click('.menus .drop [role=menuitem]:has-text("Manage")')
    await ann.click('.menus .drop [role=menuitem]:has-text("Share")')
    await ann.fill('.modal input >> nth=0', 'vera')
    await ann.fill('.modal input >> nth=1', 'Vera-has-a-Password-3')
    await ann.selectOption('.modal select', 'viewer')
    await ann.click('.modal button:has-text("Add person")')
    await ann.waitForSelector('.added')
    await ann.keyboard.press('Escape')
    const vera = await login(browser, 'plan', 'vera', 'Vera-has-a-Password-3', false)
    await wait(vera, () => [...document.querySelectorAll('.cell')].some((e) => e.textContent.trim() === 'hello'), null, 'vera sees the table')
    await vera.click('.viewport', { position: { x: 100, y: 40 } })
    await vera.keyboard.type('x')
    await wait(vera, () => document.querySelector('.toast')?.textContent.includes('only look'), null, 'viewer refusal')
    assert.equal(await vera.locator('.editor').count(), 0)
    assert.equal(await vera.locator('.menus .title:text-is("File")').count(), 1)
    console.log('viewer is told:', await vera.locator('.toast').textContent())
    // a viewer sees where others are
    await ann.click('.viewport', { position: { x: 300, y: 100 } })
    await wait(vera, () => document.querySelector('.outline'), null, 'vera sees ann’s place')
    console.log('viewer sees ann’s cursor')

    // ---- the list on the start page
    const lister = await (await browser.newContext()).newPage()
    await lister.goto(URL)
    await wait(lister, () => document.querySelector('.list li button'), null, 'document list')
    console.log('start page lists:', (await lister.locator('.list li').first().textContent()).replace(/\s+/g, ' ').trim())

    // ---- the server goes away and comes back: nobody loses anything
    server.kill('SIGTERM')
    await wait(ann, () => document.querySelector('.banner'), null, 'reconnect banner')
    await ann.screenshot({ path: `${SHOTS}/08-reconnecting.png` })
    console.log('banner:', (await ann.locator('.banner').textContent()).trim())
    await sleep(1500)
    server = startServer()
    await ready()
    await wait(ann, () => document.querySelector('.health.open') && !document.querySelector('.banner'), null, 'ann reconnected')
    await wait(vera, () => document.querySelector('.health.open'), null, 'vera reconnected')
    await wait(ann, () => [...document.querySelectorAll('.cell')].some((e) => e.textContent.trim() === 'hello'), null, 'the table is back')
    await ann.click('.viewport', { position: { x: 100, y: 120 } })
    await ann.keyboard.type('after the restart')
    await ann.keyboard.press('Enter')
    await wait(vera, () => [...document.querySelectorAll('.cell')].some((e) => e.textContent.trim() === 'after the restart'), null, 'vera sees the new cell')
    console.log('server restarted; both reconnected by themselves and keep working')

    // ---- a narrow screen
    await ann.setViewportSize({ width: 390, height: 800 })
    await sleep(300)
    await ann.screenshot({ path: `${SHOTS}/09-narrow.png` })

    for (const [n, p] of [['ann', ann], ['vera', vera]]) assert.deepEqual(p.errors, [], `${n} page errors`)
    console.log('\nALL GOOD')
  } finally {
    await browser.close()
    server.kill('SIGTERM')
    fs.rmSync(DATA, { recursive: true, force: true })
  }
})().catch((e) => {
  console.error('FAILED:', e.message)
  process.exit(1)
})
