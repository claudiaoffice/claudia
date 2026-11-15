// Description and tags on the front page, in a real browser against a real sealed server: a document is made, its owner
// writes a description and tags with Details…, anybody sees them in the list without a password, a chip narrows the
// list, and a collection can be left again with "All documents" and with Esc.
const { chromium } = require('playwright')
const { spawn } = require('node:child_process')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '../..')
const PORT = 8771
const URL = `http://127.0.0.1:${PORT}/`
const DATA = fs.mkdtempSync(path.join(os.tmpdir(), 'claudia-e2e-details-'))
const ANN = ['annabelle', 'Ann-has-a-Password-1']
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
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 900 } })).newPage()
  page.errors = []
  page.on('pageerror', (e) => page.errors.push(e.message))
  await page.goto(URL)
  return page
}
async function makeDocument(browser, id) {
  const page = await newPage(browser)
  await page.fill('input[name=document]', id)
  await page.fill('input[name=user]', ANN[0])
  await page.fill('input[name=password]', ANN[1])
  await page.click('text=Create document')
  await page.waitForSelector('[data-testid=recovery-key]')
  await page.check('.modal input[type=checkbox]')
  await page.click('.modal button:text-is("Continue")')
  await page.waitForSelector('.viewport')
  await page.close()
}

;(async () => {
  const server = startServer()
  const browser = await chromium.launch()
  try {
    await ready()
    await makeDocument(browser, 'forecast-q3')
    await makeDocument(browser, 'lab-notes')

    // ---- the owner writes a description and tags without opening the document
    const page = await newPage(browser)
    await page.waitForSelector('.list > ul > li')
    await page.click('.list > ul > li:has-text("forecast-q3") button[aria-label^="Details of"]')
    await page.fill('#edit-description', 'Cash-flow forecast, **Q3**')
    await page.fill('#edit-tag', 'Finance, forecast,')
    await page.fill('input[name=details-user]', ANN[0])
    await page.fill('input[name=details-password]', ANN[1])
    await page.click('.modal button:text-is("Save details")')
    await page.waitForSelector('.list > ul > li:has-text("forecast-q3") .chip:text-is("finance")')
    assert.match(await page.textContent('.list > ul > li:has-text("forecast-q3") .summary'), /Cash-flow forecast, Q3/)
    assert.equal(await page.locator('.list > ul > li:has-text("forecast-q3") .summary strong').count(), 1, 'bold is bold, never HTML')
    console.log('details saved and shown in the list')

    // ---- a wrong password changes nothing and says so
    await page.click('.list > ul > li:has-text("lab-notes") button[aria-label^="Details of"]')
    await page.fill('#edit-description', 'nope')
    await page.fill('input[name=details-user]', ANN[0])
    await page.fill('input[name=details-password]', 'not-the-password-1')
    await page.click('.modal button:text-is("Save details")')
    await page.waitForSelector('.modal [role=alert]')
    await page.keyboard.press('Escape')
    assert.equal(await page.locator('.list > ul > li:has-text("lab-notes") .summary.none').count(), 1)
    console.log('a wrong password changes nothing')

    // ---- anybody sees them: a fresh page, no login, and the search finds the description and the tag
    const other = await newPage(browser)
    await other.waitForSelector('.list > ul > li')
    await other.fill('input[name=search]', 'cash-flow')
    assert.equal(await other.locator('.list > ul > li').count(), 1)
    await other.fill('input[name=search]', 'finance')
    assert.equal(await other.locator('.list > ul > li').count(), 1)
    await other.fill('input[name=search]', '')
    await other.click('.list > ul > li:has-text("forecast-q3") .chip:text-is("finance")')
    assert.equal(await other.locator('.list > ul > li').count(), 1, 'a chip narrows the list')
    await other.selectOption('[data-testid=tag-filter]', '')
    assert.equal(await other.locator('.list > ul > li').count(), 2, '"all tags" lets go of it')
    console.log('search, chips and the tag filter work for everybody')

    // ---- leaving a collection: the way back is visible, and Esc does it too
    await other.click('.list > ul > li:has-text("forecast-q3") button[aria-label^="Collections of"]')
    await other.fill('.collection-menu input', 'Budget')
    await other.press('.collection-menu input', 'Enter')
    await other.click('button:has-text("Budget")')
    await other.waitForSelector('[data-testid=all-documents]')
    await other.click('[data-testid=all-documents]')
    assert.equal(await other.locator('[data-testid=all-documents]').count(), 0)
    await other.click('button:has-text("Budget")')
    await other.waitForSelector('[data-testid=all-documents]')
    await other.keyboard.press('Escape')
    assert.equal(await other.locator('[data-testid=all-documents]').count(), 0, 'Esc is the way back, too')
    console.log('a collection can be left again')

    for (const p of [page, other]) assert.deepEqual(p.errors, [], 'no page errors')
    console.log('ok')
  } finally {
    await browser.close()
    server.kill('SIGTERM')
  }
})().catch((error) => {
  console.error(error)
  process.exit(1)
})
