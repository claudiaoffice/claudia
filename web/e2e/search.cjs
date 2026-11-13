// Edit ▸ Search & Replace… in a real browser (E5.15): the quick field, the marks in the grid, the builder with its
// sentence, replacing in one undoable step, and the person's own pattern with its error in words.
const { chromium } = require('playwright')
const { spawn } = require('node:child_process')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '../..')
const PORT = Number(process.env.PORT ?? 8768)
const URL = `http://127.0.0.1:${PORT}/`
const DATA = fs.mkdtempSync(path.join(os.tmpdir(), 'claudia-e2e-search-'))
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `search-${Date.now() % 100000}`
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (...a) => console.log(...a)

function startServer() {
  const out = process.env.SERVER_LOG ? fs.openSync(process.env.SERVER_LOG, 'a') : 'ignore'
  return spawn(
    path.join(ROOT, '.venv/bin/python'),
    ['-m', 'claudia_server', '--no-tls', '--port', String(PORT), '--dir', DATA, '--web', path.join(ROOT, 'web/.output/public')],
    { cwd: ROOT, stdio: ['ignore', out, out] },
  )
}
async function ready() {
  for (let i = 0; i < 60; i++) {
    try {
      if ((await fetch(URL + 'api/health')).ok) return
    } catch {
      // not up yet
    }
    await sleep(200)
  }
  throw new Error('the server did not start')
}
async function cellAt(page, row, col) {
  const box = await page.locator('.viewport').boundingBox()
  return { x: box.x + 52 + col * 96 + 40, y: box.y + 26 + row * 26 + 13 }
}
async function click(page, row, col) {
  const p = await cellAt(page, row, col)
  await page.mouse.click(p.x, p.y)
}
async function type(page, row, col, input) {
  await click(page, row, col)
  await page.keyboard.type(input)
  await page.keyboard.press('Enter')
}
async function text(page, row, col) {
  const p = await cellAt(page, row, col)
  return page.evaluate(({ x, y }) => {
    const cell = [...document.querySelectorAll('.cell')].find((c) => {
      const r = c.getBoundingClientRect()
      return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom
    })
    return cell ? cell.textContent.trim() : ''
  }, p)
}
async function waitCell(page, row, col, expected) {
  for (let i = 0; i < 60; i++) {
    if ((await text(page, row, col)) === expected) return
    await sleep(100)
  }
  throw new Error(`cell ${row},${col} is ${JSON.stringify(await text(page, row, col))}, not ${expected}`)
}
const summary = (page) => page.locator('[data-testid=search-summary]')
async function waitSummary(page, expected) {
  await page.waitForFunction(
    ([sel, want]) => document.querySelector(sel)?.textContent.trim() === want,
    ['[data-testid=search-summary]', expected],
    { timeout: 10000 },
  ).catch(async () => {
    throw new Error(`the summary is ${JSON.stringify(await summary(page).textContent())}, not ${JSON.stringify(expected)}`)
  })
}

;(async () => {
  fs.mkdirSync(SHOTS, { recursive: true })
  const server = startServer()
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM })
  const errors = []
  try {
    await ready()
    const page = await (await browser.newContext({ viewport: { width: 1360, height: 800 } })).newPage()
    page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
    page.on('console', (m) => m.type() === 'error' && errors.push('console: ' + m.text()))
    await page.goto(URL)
    await page.fill('input[name=document]', DOC)
    await page.fill('input[name=user]', 'ann')
    await page.fill('input[name=password]', 'Ann-has-a-Password-1')
    await page.click('text=Create document')
    await page.waitForSelector('[data-testid=recovery-key]')
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
    await page.waitForSelector('.viewport')
    await page.waitForFunction(() => document.querySelector('.health.open'))

    await type(page, 0, 0, 'Cost EUR')
    await type(page, 1, 0, 'Fee EUR')
    await type(page, 2, 0, 'Note')
    await type(page, 0, 1, '=LEN(A1)')
    await type(page, 1, 1, '5')
    await waitCell(page, 0, 1, '8')

    // 1. Ctrl+F opens the panel, with the focus in the quick field; the cells that match are marked
    await click(page, 4, 4)
    await page.keyboard.press('Control+f')
    await page.waitForSelector('[data-testid=search-panel]')
    assert.ok(await page.locator('[data-testid=search-quick]').evaluate((el) => el === document.activeElement), 'focus is in the field')
    await page.keyboard.type('EUR')
    await waitSummary(page, '2 matches')
    assert.equal(await page.locator('[data-search-mark]').count(), 2, 'two cells are marked')
    await page.screenshot({ path: path.join(SHOTS, 'search-quick.png') })
    log('ok quick find marks both cells')

    // 2. Enter goes to the first match, and makes it the current one
    await page.keyboard.press('Enter')
    await page.waitForSelector('[data-search-mark=current]')
    log('ok Enter goes to a match')

    // 3. nothing matches: said so
    await page.fill('[data-testid=search-quick]', 'zzz')
    await waitSummary(page, 'No matches')
    await page.fill('[data-testid=search-quick]', 'EUR')
    await waitSummary(page, '2 matches')

    // 4. replace: the preview, then one step that Undo takes back
    await page.click('button:text-is("Replace with… ›")').catch(() => page.click('text=Replace with…'))
    await page.fill('input[data-replace-first]', 'USD')
    await page.waitForSelector('[data-testid=search-replace-all]:not([disabled])')
    assert.match(await page.locator('[data-testid=search-replace-all]').textContent(), /Replace all 2/)
    await page.screenshot({ path: path.join(SHOTS, 'search-replace.png') })
    await page.click('[data-testid=search-replace-all]')
    await waitCell(page, 0, 0, 'Cost USD')
    await waitCell(page, 1, 0, 'Fee USD')
    log('ok replaced in two cells')
    await click(page, 4, 4)
    await page.keyboard.press('Control+z')
    await waitCell(page, 0, 0, 'Cost EUR')
    await waitCell(page, 1, 0, 'Fee EUR')
    log('ok one Undo brings both back')

    // 5. the builder says in a sentence what it finds
    await page.keyboard.press('Control+f')
    await page.locator('[data-testid=search-quick]').waitFor({ state: 'visible' }).catch(() => {})
    await page.click('text=Build a pattern…').catch(async () => {
      await page.click('button[aria-label="More"]')
    })
    await page.waitForSelector('[data-testid=search-sentence]')
    await waitSummary(page, '2 matches')
    const said = await page.locator('[data-testid=search-sentence]').textContent()
    assert.match(said, /Finds the text “EUR”/, said)
    await page.screenshot({ path: path.join(SHOTS, 'search-builder.png') })
    log('ok builder sentence:', said)

    // 6. the person's own pattern: a mistake is explained in words, with its place
    await page.click('button[aria-label="More"]')
    await page.click('button:text-is("Write the pattern yourself…")')
    await page.fill('[data-pattern-find]', '(EUR')
    await page.waitForSelector('.error[role=alert]')
    const problem = await page.locator('.error[role=alert]').textContent()
    assert.match(problem, /“\(”/, problem)
    assert.doesNotMatch(await page.locator('[data-testid=search-panel]').textContent(), /regular expression|regex/i, 'the words never show')
    await page.screenshot({ path: path.join(SHOTS, 'search-pattern-error.png') })
    log('ok pattern error:', problem.replace(/\s+/g, ' '))
    await page.fill('[data-pattern-find]', 'E.R')
    await waitSummary(page, '2 matches')

    // 7. Esc closes the panel and the marks go with it
    await page.keyboard.press('Escape')
    await page.waitForSelector('[data-testid=search-panel]', { state: 'detached' })
    assert.equal(await page.locator('[data-search-mark]').count(), 0)
    log('ok Esc closes it')

    assert.deepEqual(errors, [], 'no errors in the browser')
    log('search e2e passed')
  } finally {
    await browser.close()
    server.kill()
  }
})().catch((e) => {
  console.error(e)
  process.exit(1)
})
