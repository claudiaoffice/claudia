// The recovery key in a real browser against a real sealed server: shown once when a document is made, replaced by the
// owner, and the way back in for somebody who forgot their password. Then the server restarts, and the folder is read
// for anything it should not hold.
const { chromium } = require('playwright')
const { spawn } = require('node:child_process')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '../..')
const PORT = 8767
const URL = `http://127.0.0.1:${PORT}/`
const DATA = fs.mkdtempSync(path.join(os.tmpdir(), 'claudia-e2e-recovery-'))
const ANN = ['annabelle', 'Ann-has-a-Password-1']
const BEN = ['bertram', 'Ben-has-a-Password-2']
const BEN_NEW = 'Ben-Starts-Afresh-9'
const SECRET = 'the-launch-budget-4711'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function startServer() {
  return spawn(
    path.join(ROOT, '.venv/bin/python'),
    ['-m', 'claudia_server', '--no-tls', '--port', String(PORT), '--dir', DATA, '--web', path.join(ROOT, 'web/.output/public')],
    { cwd: ROOT, stdio: 'ignore' },
  )
}
async function ready() {
  for (let i = 0; i < 50; i++) {
    try {
      if ((await fetch(URL + 'api/health')).ok) return
    } catch {
      // not up yet: try again
    }
    await sleep(200)
  }
  throw new Error('the server did not start')
}
async function stop(server) {
  server.kill('SIGTERM')
  await new Promise((resolve) => server.once('exit', resolve))
}
async function newPage(browser) {
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 800 } })).newPage()
  page.errors = []
  page.on('pageerror', (e) => page.errors.push(e.message))
  await page.goto(URL)
  return page
}
async function fill(page, doc, user, password) {
  await page.fill('input[name=document]', doc)
  await page.fill('input[name=user]', user)
  await page.fill('input[name=password]', password)
}
async function inside(page) {
  await page.waitForSelector('.viewport')
  await page.waitForFunction(() => document.querySelector('.health.open'))
}
const keyOf = (page) => page.$$eval('[data-testid=recovery-key] code', (els) => els.map((e) => e.textContent.trim()).join('-'))
const wait = (page, fn, arg, what) => page.waitForFunction(fn, arg, { timeout: 15000 }).catch(() => Promise.reject(new Error('timed out: ' + what)))

;(async () => {
  let server = startServer()
  const browser = await chromium.launch()
  try {
    await ready()

    // ---- a new document shows its recovery key, and will not let the person go in before it is acknowledged
    const ann = await newPage(browser)
    await fill(ann, 'plan', ...ANN)
    await ann.click('text=Create document')
    await ann.waitForSelector('[data-testid=recovery-key]')
    const first = await keyOf(ann)
    assert.match(first, /^([A-Z2-7]{4}-){12}[A-Z2-7]{4}$/, 'thirteen groups of four')
    assert.equal(await ann.locator('.viewport').count(), 0, 'the document is not shown before the key is acknowledged')
    assert.ok(await ann.locator('.modal button:text-is("Continue")').isDisabled(), 'Continue waits for the tick')
    await ann.keyboard.press('Escape')
    assert.equal(await ann.locator('[data-testid=recovery-key]').count(), 1, 'Escape does not dismiss it')
    await ann.check('.modal input[type=checkbox]')
    await ann.click('.modal button:text-is("Continue")')
    await inside(ann)
    assert.equal(await ann.locator('[data-testid=recovery-key]').count(), 0, 'the key is gone from the page')
    assert.ok(!(await ann.content()).includes(first), 'and nowhere in it')
    console.log('recovery key shown once:', first.slice(0, 9) + '…')

    // ---- some work, so that there is something to protect
    await ann.click('.viewport', { position: { x: 100, y: 40 } })
    await ann.keyboard.type(SECRET)
    await ann.keyboard.press('Enter')
    await wait(ann, () => [...document.querySelectorAll('.cell')].some((e) => e.textContent.includes('launch')), null, 'first cell')

    // ---- the owner adds Ben, and makes a new key; the first one stops working
    await ann.click('.menus .title:text-is("File")')
    await ann.click('.menus .drop [role=menuitem]:has-text("Manage")')
    await ann.click('.menus .drop [role=menuitem]:has-text("Share")')
    await ann.fill('.modal input >> nth=0', BEN[0])
    await ann.fill('.modal input >> nth=1', BEN[1])
    await ann.click('.modal button:has-text("Add person")')
    await ann.waitForSelector('.added')
    await ann.click('.modal button:has-text("Make a new recovery key")')
    await ann.waitForSelector('[data-testid=recovery-key]')
    const second = await keyOf(ann)
    assert.notEqual(second, first)
    await ann.check('.modal input[type=checkbox]')
    await ann.click('.modal button:text-is("Continue")')
    await ann.waitForSelector('.modal:has-text("Share this document")')
    await ann.keyboard.press('Escape')
    console.log('a new key was made')

    // ---- Ben is not allowed to make one
    const ben = await newPage(browser)
    await fill(ben, 'plan', ...BEN)
    await ben.click('button:text-is("Open")')
    await inside(ben)
    await ben.click('.menus .title:text-is("File")')
    await ben.click('.menus .drop [role=menuitem]:has-text("Manage")')
    assert.ok(await ben.locator('.menus .drop [role=menuitem]:has-text("Share")').isDisabled(), 'only the owner may share, and so make a key')
    await ben.close()

    // ---- the restart: everything sealed, nothing readable, then Ben forgets his password
    await ann.close()
    await stop(server)
    const bytes = []
    for (const file of fs.readdirSync(path.join(DATA, 'docs'), { recursive: true })) {
      const full = path.join(DATA, 'docs', file)
      if (fs.statSync(full).isFile()) bytes.push(fs.readFileSync(full))
    }
    const all = Buffer.concat(bytes)
    for (const text of [SECRET, first, second, first.replaceAll('-', ''), second.replaceAll('-', ''), ANN[1], BEN[1], ANN[0], BEN[0]])
      assert.ok(!all.includes(Buffer.from(text)), `the folder holds ${text.slice(0, 6)}…`)
    console.log('the folder holds none of the content, names, passwords or keys')

    server = startServer()
    await ready()
    const lost = await newPage(browser)
    await lost.click('text=I forgot my password')
    await fill(lost, 'plan', BEN[0], BEN_NEW)
    await lost.fill('input[name=recovery-key]', first)
    await lost.click('button:text-is("Get back in")')
    await lost.waitForSelector('[role=alert]')
    assert.match(await lost.locator('[role=alert]').textContent(), /does not fit this document/)
    console.log('the old key is turned away')

    await lost.fill('input[name=recovery-key]', second.toLowerCase().replaceAll('-', ' ')) // typed in any style
    await lost.click('button:text-is("Get back in")')
    await inside(lost)
    await wait(lost, (t) => [...document.querySelectorAll('.cell')].some((e) => e.textContent.includes(t)), 'launch', 'the work is there')
    console.log('Ben is back in with the new key, and sees the work')
    await lost.close()

    // ---- the old password is gone, the new one works, and the key does not give a stranger the document by name
    const again = await newPage(browser)
    await fill(again, 'plan', BEN[0], BEN[1])
    await again.click('button:text-is("Open")')
    await again.waitForSelector('[role=alert]')
    await fill(again, 'plan', BEN[0], BEN_NEW)
    await again.click('button:text-is("Open")')
    await inside(again)
    console.log('old password refused, new password works')
    await again.close()

    console.log('\nALL GOOD')
  } catch (error) {
    console.log('FAILED:', error.message)
    process.exitCode = 1
  } finally {
    await browser.close()
    server.kill('SIGTERM')
    fs.rmSync(DATA, { recursive: true, force: true })
  }
})()
