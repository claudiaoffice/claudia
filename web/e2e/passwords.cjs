// Passwords in a real browser against a real sealed server (sheet 12, D448): the eye shows and hides what was typed
// and starts hidden again in a new dialog; Share's password for a colleague starts hidden; File ▸ Manage ▸ Change
// Password… with a wrong current password says so in the dialog, with a right one changes it, and only the new one
// opens the document afterwards.
const { chromium } = require('playwright')
const { spawn } = require('node:child_process')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '../..')
const PORT = 8768
const URL = `http://127.0.0.1:${PORT}/`
const DATA = fs.mkdtempSync(path.join(os.tmpdir(), 'claudia-e2e-passwords-'))
const ANN = ['annabelle', 'Ann-has-a-Password-1']
const ANN_NEW = 'Ann-Chose-Another-2'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function startServer() {
  return spawn(
    path.join(ROOT, '.venv/bin/python'),
    ['-m', 'claudia_server', '--no-tls', '--apps', 'computes', '--port', String(PORT), '--dir', DATA, '--web', path.join(ROOT, 'web/.output/public')],
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
async function newPage(browser) {
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 800 } })).newPage()
  page.errors = []
  page.on('pageerror', (e) => page.errors.push(e.message))
  await page.goto(URL)
  return page
}
async function fill(page, user, password) {
  await page.fill('input[name=document]', 'plan')
  await page.fill('input[name=user]', user)
  await page.fill('input[name=password]', password)
}
const typeOf = (page, selector) => page.getAttribute(selector, 'type')

;(async () => {
  const server = startServer()
  const browser = await chromium.launch()
  try {
    await ready()
    const ann = await newPage(browser)

    // ---- the eye on the front page
    await fill(ann, ...ANN)
    assert.equal(await typeOf(ann, 'input[name=password]'), 'password', 'a password starts hidden')
    const eye = ann.locator('input[name=password] + button.eye')
    assert.equal(await eye.getAttribute('aria-pressed'), 'false')
    assert.equal(await eye.getAttribute('aria-label'), 'Show password')
    await eye.click()
    assert.equal(await typeOf(ann, 'input[name=password]'), 'text', 'the eye shows it')
    assert.equal(await eye.getAttribute('aria-pressed'), 'true')
    await ann.focus('input[name=password]')
    await ann.keyboard.press('Tab')
    assert.equal(await ann.evaluate(() => document.activeElement?.classList.contains('eye')), true, 'Tab reaches the eye')
    await ann.keyboard.press('Space')
    assert.equal(await typeOf(ann, 'input[name=password]'), 'password', 'Space hides it again')
    assert.equal(await ann.inputValue('input[name=password]'), ANN[1], 'and nothing was submitted or lost')

    // ---- make the document
    await ann.click('text=Create document')
    await ann.waitForSelector('[data-testid=recovery-key]')
    await ann.check('.modal input[type=checkbox]')
    await ann.click('.modal button:text-is("Continue")')
    await ann.waitForSelector('.viewport')

    // ---- Share: the colleague's password starts hidden too
    await ann.keyboard.press('Control+Alt+Shift+S')
    await ann.waitForSelector('input[name=share-password]')
    assert.equal(await typeOf(ann, 'input[name=share-password]'), 'password', "a colleague's password starts hidden")
    await ann.keyboard.press('Escape')

    // ---- Change Password… by its key: a wrong current password is said in the dialog
    await ann.keyboard.press('Control+Alt+Shift+W')
    await ann.waitForSelector('input[name=current-password]')
    await ann.fill('input[name=current-password]', 'Not-My-Password-3')
    await ann.fill('input[name=new-password]', ANN_NEW)
    await ann.click('.modal button:text-is("Change password")')
    await ann.waitForSelector('.modal .error')
    assert.match(await ann.textContent('.modal .error'), /current password/)
    // ... the right one changes it
    await ann.fill('input[name=current-password]', ANN[1])
    await ann.click('.modal button:text-is("Change password")')
    await ann.waitForSelector('input[name=current-password]', { state: 'detached' })
    await ann.waitForFunction(() => /is changed/.test(document.querySelector('.toast')?.textContent ?? ''))
    // ... and the dialog's fields start hidden again when it opens anew
    await ann.keyboard.press('Control+Alt+Shift+W')
    await ann.waitForSelector('input[name=new-password]')
    assert.equal(await typeOf(ann, 'input[name=new-password]'), 'password')
    await ann.keyboard.press('Escape')

    // ---- only the new password opens the document now
    const again = await newPage(browser)
    await fill(again, ANN[0], ANN[1])
    await again.click('form button:text-is("Open")')
    await again.waitForSelector('form .error')
    assert.match(await again.textContent('form .error'), /not right/, 'the old password no longer opens it')
    await fill(again, ANN[0], ANN_NEW)
    await again.click('form button:text-is("Open")')
    await again.waitForSelector('.viewport')

    assert.deepEqual([...ann.errors, ...again.errors], [], 'no page errors')
    console.log('passwords: ok')
  } finally {
    await browser.close()
    server.kill('SIGTERM')
  }
})().catch((error) => {
  console.error(error)
  process.exit(1)
})
