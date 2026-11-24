// The computes grid, as a screen reader meets it (UX-02, BITV 4.1.2): its structure in ARIA, the name of the cell the
// focus is on, what is said of a range, and axe-core's verdict on the whole workspace page. Then the landmarks of the
// document page of each app (UX-32): one `main`, and nothing outside a landmark, in composes and creates as well.
//   uv run python scripts/start.py --app computes --port 8765 --no-browser --rebuild --dir /tmp/claudia-axe
//   node e2e/grid-a11y.cjs        (CLAUDIA_CHROMIUM=/path/to/chrome when playwright's own chromium is not installed)
//   (COMPOSES and CREATES are the addresses of a composes and a creates server, 8766 and 8767 by default)
const { launch } = require('./browser.cjs')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const URL = process.env.URL ?? 'http://127.0.0.1:8765/'
const COMPOSES = process.env.COMPOSES ?? 'http://127.0.0.1:8766/'
const CREATES = process.env.CREATES ?? 'http://127.0.0.1:8767/'
const DOC = `axe-${Date.now() % 100000}`
const AXE = fs.readFileSync(path.join(__dirname, '..', 'node_modules', 'axe-core', 'axe.min.js'), 'utf8')
const log = (...a) => console.log(...a)

const cell = (page, row, col) => page.locator(`[role=gridcell][id$="-r${row}c${col}"]`)
async function activeLabel(page) {
  return page.evaluate(() => {
    const grid = document.querySelector('[role=grid]')
    const id = grid.getAttribute('aria-activedescendant')
    const el = id && document.getElementById(id)
    return el ? { id, label: el.getAttribute('aria-label'), role: el.getAttribute('role'), text: el.textContent.trim() } : null
  })
}
async function toA1(page) {
  await page.keyboard.press('Home')
  for (let i = 0; i < 6; i++) await page.keyboard.press('ArrowUp')
}
async function typeInto(page, text) {
  await page.keyboard.type(text)
  await page.keyboard.press('Enter')
}

/** A new document on the server at `url`, opened, in a page of its own. */
async function create(context, url) {
  const page = await context.newPage()
  await page.goto(url)
  await page.fill('input[name=document]', DOC)
  await page.fill('input[name=user]', 'ann')
  await page.fill('input[name=password]', 'Ann-has-a-Password-1')
  await page.click('text=Create document')
  await page.waitForSelector('[data-testid=recovery-key]')
  await page.check('.modal input[type=checkbox]')
  await page.click('.modal button:text-is("Continue")')
  await page.waitForFunction(() => document.querySelector('.health.open'))
  return page
}

/** axe's landmark rules (best practice, not WCAG: UX-32) on the page as it is: the ids of those that fail, and where. */
async function landmarkFaults(page) {
  if (!(await page.evaluate(() => 'axe' in window))) await page.addScriptTag({ content: AXE })
  return page.evaluate(() =>
    window.axe.run(document, { runOnly: { type: 'rule', values: ['landmark-one-main', 'region'] } }).then((r) =>
      r.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target.join(' ')).slice(0, 6) })),
    ),
  )
}

;(async () => {
  const browser = await launch()
  const context = await browser.newContext({ viewport: { width: 1360, height: 800 }, bypassCSP: true }) // only so that axe can be injected
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push('console: ' + m.text()))
  try {
    await page.goto(URL)
    await page.fill('input[name=document]', DOC)
    await page.fill('input[name=user]', 'ann')
    await page.fill('input[name=password]', 'Ann-has-a-Password-1')
    await page.click('text=Create document')
    await page.waitForSelector('[data-testid=recovery-key]')
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
    await page.waitForSelector('[role=grid]')
    await page.waitForFunction(() => document.querySelector('.health.open'))

    // some content, typed from the keyboard alone: a label, a number, a formula and an error
    await page.locator('[role=grid]').focus()
    await typeInto(page, 'Rent') // A1, then down
    await typeInto(page, 'Food') // A2
    await page.keyboard.press('ArrowRight')
    await page.keyboard.press('ArrowUp')
    await page.keyboard.press('ArrowUp')
    await typeInto(page, '800') // B1
    await typeInto(page, '=B1*12') // B2
    await typeInto(page, '=1/0') // B3
    await page.waitForFunction(() => document.body.textContent.includes('9600'))

    // -- structure
    const grid = page.locator('[role=grid]')
    assert.equal(await grid.getAttribute('aria-rowcount'), '10001')
    assert.equal(await grid.getAttribute('aria-colcount'), '703')
    assert.equal(await grid.getAttribute('aria-multiselectable'), 'true')
    assert.ok((await grid.getAttribute('aria-label')).length > 0, 'the grid has a name')
    assert.equal(await page.locator('[role=row][aria-rowindex="1"] [role=columnheader]').first().textContent(), 'A')
    assert.equal(await page.locator('[role=row][aria-rowindex="3"] [role=rowheader]').textContent(), '2')
    assert.equal(await cell(page, 1, 1).getAttribute('aria-colindex'), '3')
    const owner = await cell(page, 1, 1).evaluate((el) => el.closest('[role=row]').getAttribute('aria-rowindex'))
    assert.equal(owner, '3', 'a cell sits in the row with its own index')

    // -- the active cell is named, empty or not, and moves with the keys
    await toA1(page)
    let now = await activeLabel(page)
    assert.equal(now.role, 'gridcell')
    assert.match(now.label, /^A1, Rent$/)
    await page.keyboard.press('ArrowRight')
    now = await activeLabel(page)
    assert.match(now.label, /^B1, 800$/)
    await page.keyboard.press('ArrowDown')
    assert.match((await activeLabel(page)).label, /^B2, 9600, formula$/)
    await page.keyboard.press('ArrowDown')
    assert.match((await activeLabel(page)).label, /^B3, error #DIV\/0!/)
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('ArrowDown')
    assert.match((await activeLabel(page)).label, /^B5, empty$/, 'an empty cell is still a cell to land on')
    assert.equal(await cell(page, 4, 1).getAttribute('aria-selected'), 'true')

    // -- a range is said once it has settled
    await toA1(page)
    await page.keyboard.press('Shift+ArrowRight')
    await page.keyboard.press('Shift+ArrowDown')
    await page.waitForFunction(() => document.querySelector('[role=status][aria-live=polite].sr-only')?.textContent.includes('A1:B2 selected, 4 cells'), null, { timeout: 4000 })
    await page.keyboard.press('ArrowDown')

    // -- axe, on the page as it is
    await page.addScriptTag({ content: AXE })
    const result = await page.evaluate(() =>
      window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } }).then((r) => ({
        violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.map((n) => ({ target: n.target.join(' '), summary: n.failureSummary })).slice(0, 4), count: v.nodes.length })),
        incomplete: r.incomplete.map((v) => ({ id: v.id, count: v.nodes.length, first: v.nodes.slice(0, 2).map((n) => n.target.join(' ')) })),
      })),
    )
    log('axe incomplete (needs a person to judge):', JSON.stringify(result.incomplete))
    if (result.violations.length) log('axe violations:\n' + JSON.stringify(result.violations, null, 2))
    assert.deepEqual(result.violations.map((v) => v.id), [], 'axe finds nothing to fix')

    // -- the landmarks of the document page, in each app: one main, and no content outside a landmark (UX-32)
    assert.deepEqual(await landmarkFaults(page), [], 'computes: one main, and every part in a landmark')
    for (const [app, url] of [['composes', COMPOSES], ['creates', CREATES]]) {
      const other = await create(context, url)
      other.on('pageerror', (e) => errors.push(`${app} pageerror: ${e.message}`))
      assert.deepEqual(await landmarkFaults(other), [], `${app}: one main, and every part in a landmark`)
    }
    assert.deepEqual(errors, [])
    log('grid-a11y: ok')
  } catch (e) {
    await page.screenshot({ path: '/tmp/grid-a11y-fail.png' }).catch(() => undefined)
    console.error(e)
    process.exitCode = 1
  } finally {
    await browser.close()
  }
})()
