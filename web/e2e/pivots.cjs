// Tools ▸ Pivot Table… in a real browser (E6.30, D624): make a pivot table from a named table, fill it with the field
// panel (ticks, a chip's ▾ menu), watch it follow the source, change a value field, look at its SQL, delete it and take
// the deletion back. Every step by keyboard or by the controls the person sees; no mock of the server.
const { chromium } = require('playwright')
const { spawn } = require('node:child_process')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '../..')
const PORT = Number(process.env.PORT ?? 8769)
const URL = `http://127.0.0.1:${PORT}/`
const DATA = fs.mkdtempSync(path.join(os.tmpdir(), 'claudia-e2e-pivots-'))
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `pivots-${Date.now() % 100000}`
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (...a) => console.log(...a)

function startServer() {
  const out = process.env.SERVER_LOG ? fs.openSync(process.env.SERVER_LOG, 'a') : 'ignore'
  return spawn(
    path.join(ROOT, '.venv/bin/python'),
    ['-m', 'claudia_server', '--no-tls', '--apps', 'computes', '--port', String(PORT), '--dir', DATA, '--web', path.join(ROOT, 'web/.output/public')],
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
  let last
  for (let i = 0; i < 80; i++) {
    last = await text(page, row, col)
    if (last === expected) return
    await sleep(100)
  }
  throw new Error(`cell ${row},${col} is ${JSON.stringify(last)}, not ${JSON.stringify(expected)}`)
}
const fills = (page) => page.locator('[data-testid=pivot-fills]')
async function waitFills(page, pattern) {
  for (let i = 0; i < 80; i++) {
    if (pattern.test(await fills(page).textContent())) return
    await sleep(100)
  }
  throw new Error(`the fills line is ${JSON.stringify(await fills(page).textContent())}, not ${pattern}`)
}
const tick = (page, field) => page.locator(`[data-testid=pivot-panel] .fields li:has(.field:text-is("${field}")) input`)

;(async () => {
  fs.mkdirSync(SHOTS, { recursive: true })
  const server = startServer()
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM })
  const errors = []
  try {
    await ready()
    const page = await (await browser.newContext({ viewport: { width: 1400, height: 820 } })).newPage()
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

    // 1. a table: a header row and six rows of data, named Sales
    const rows = [
      ['Region', 'Quarter', 'Amount'],
      ['East', 'Q1', '100'],
      ['East', 'Q2', '200'],
      ['West', 'Q1', '50'],
      ['West', 'Q2', '70'],
      ['North', 'Q1', '30'],
      ['North', 'Q2', '40'],
    ]
    for (let r = 0; r < rows.length; r++) for (let c = 0; c < 3; c++) await type(page, r, c, rows[r][c])
    await click(page, 0, 0)
    for (let i = 0; i < 6; i++) await page.keyboard.press('Shift+ArrowDown')
    for (let i = 0; i < 2; i++) await page.keyboard.press('Shift+ArrowRight')
    await page.fill('input[aria-label=cell]', 'Sales')
    await page.keyboard.press('Enter')
    await page.waitForSelector('[data-testid=name-define]')
    await page.click('[data-testid=name-define] button:text-is("Define")')
    await page.waitForSelector('[data-testid=name-define]', { state: 'detached' })
    log('ok a table called Sales')

    // 2. Tools ▸ Pivot Table… (Ctrl+Alt+V): the table the cursor is in is the source
    await click(page, 2, 1)
    await page.keyboard.press('Control+Alt+v')
    await page.waitForSelector('[data-testid=pivot-create]')
    assert.equal(await page.locator('[data-testid=pivot-create] select').inputValue(), 'Sales')
    assert.equal(await page.locator('[data-testid=pivot-create] input.mono').first().inputValue(), 'SalesPivot')
    await page.screenshot({ path: path.join(SHOTS, 'pivot-create.png') })
    await page.click('[data-testid=pivot-create] button:text-is("Create")')
    await page.waitForSelector('[data-testid=pivot-panel]')
    assert.match(await page.locator('[data-testid=pivot-name]').textContent(), /SalesPivot/)
    log('ok made a pivot table, the panel is open')

    // 3. the field panel: ticking a text field puts it in Rows, then Columns; a number goes to Values
    await tick(page, 'Region').check()
    await tick(page, 'Quarter').check()
    await tick(page, 'Amount').check()
    await waitFills(page, /Fills .*A1:D6/)
    await page.screenshot({ path: path.join(SHOTS, 'pivot-panel.png') })
    await waitCell(page, 0, 0, 'Sum of Amount')
    await waitCell(page, 1, 0, 'Region')
    await waitCell(page, 1, 1, 'Q1')
    await waitCell(page, 2, 0, 'East')
    await waitCell(page, 2, 1, '100')
    await waitCell(page, 2, 3, '300')
    await waitCell(page, 5, 0, 'Total')
    await waitCell(page, 5, 3, '490')
    assert.ok((await page.locator('[data-pivot-role=total]').count()) >= 2, 'the totals are drawn as totals')
    assert.ok((await page.locator('[data-pivot-role=header]').count()) >= 2, 'the headers are drawn as headers')
    log('ok the pivot table is there, with totals')

    // 4. Esc closes the panel
    await page.keyboard.press('Escape')
    await page.waitForSelector('[data-testid=pivot-panel]', { state: 'detached' })
    log('ok Esc closes the panel')

    // 5. a cell of the pivot table, Ctrl+Shift+Alt+U: the value field's settings
    await click(page, 2, 1)
    await page.keyboard.press('Control+Shift+Alt+u')
    await page.waitForSelector('[data-testid=pivot-value]')
    await page.locator('[data-testid=pivot-value] input[type=radio][value=average]').check()
    await page.screenshot({ path: path.join(SHOTS, 'pivot-value.png') })
    await page.click('[data-testid=pivot-value] button:text-is("Apply")')
    await waitCell(page, 0, 0, 'Average of Amount')
    await waitCell(page, 2, 1, '100')
    await waitCell(page, 2, 3, '150')
    log('ok Value Field Settings: Average')

    // 6. Pivot Fields (Ctrl+Shift+Alt+M) shows the panel again; a chip's ▾ menu moves a field
    await page.keyboard.press('Control+Shift+Alt+m')
    await page.waitForSelector('[data-testid=pivot-panel]')
    await page.locator('[data-testid=pivot-panel] button[aria-label^="Quarter: move"]').click()
    await page.click('[role=menuitem]:has-text("Move to Filters")')
    await waitFills(page, /Fills .*A1:B/)
    assert.equal(await page.locator('[data-testid=pivot-panel] [data-zone=filters] .chip').count(), 1)
    assert.equal(await page.locator('[data-testid=pivot-panel] [data-zone=columns] .chip').count(), 0)
    log('ok a chip moved with its menu')

    // 7. Show as SQL…
    await page.click('[data-testid=pivot-panel] button:text-is("Show as SQL…")')
    await page.waitForSelector('[data-testid=pivot-sql]')
    // the dialog opens at once and the query follows when the server has answered: wait for it, do not read it once
    await page.waitForFunction(() => /SELECT/.test(document.querySelector('[data-testid=pivot-sql] .code')?.textContent ?? ''))
    assert.match(await page.locator('[data-testid=pivot-sql] .code').textContent(), /SELECT/)
    await page.screenshot({ path: path.join(SHOTS, 'pivot-sql.png') })
    await page.click('[data-testid=pivot-sql] button:text-is("Close")')
    await page.waitForSelector('[data-testid=pivot-sql]', { state: 'detached' })
    log('ok the query is shown')

    // 8. Delete Pivot Table… asks first; the cells go empty; Undo brings the pivot table back
    await page.keyboard.press('Escape')
    await click(page, 2, 0)
    await page.keyboard.press('Control+Shift+Alt+v')
    await page.waitForSelector('[data-testid=pivot-delete]')
    await page.click('[data-testid=pivot-delete] button:text-is("Delete")')
    await page.waitForSelector('[data-testid=pivot-delete]', { state: 'detached' })
    await waitCell(page, 1, 0, '')
    await waitCell(page, 2, 0, '')
    await click(page, 8, 8)
    await page.keyboard.press('Control+z')
    await waitCell(page, 1, 0, 'East') // one header row now that no field is across
    await waitCell(page, 2, 0, 'North')
    log('ok deleted, and undone')

    assert.deepEqual(errors, [], 'no errors in the browser')
    log('pivots e2e passed')
  } finally {
    await browser.close()
    server.kill()
  }
})().catch((e) => {
  console.error(e)
  process.exit(1)
})
