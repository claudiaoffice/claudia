// A slide among the sheets of a workbook in a real browser (E6.31 step 2, D1471, D1473): the tabs are one list, a slide
// is shown with creates' slide view and tool bar (no Present, no formula bar), a text box is put on it and taken back,
// and File ▸ Print… prints the slide shown as one landscape page and the whole workbook with the slide between the sheets.
// Nothing in the UI makes a slide yet (a chart will, E6.31 step 3), so the workbook comes in as a Claudia export made
// here with the slide in it (D1272). Run against a computes server: URL=http://127.0.0.1:8765/ npm run e2e:computes-slides
const { chromium } = require('playwright')
const { execFileSync } = require('node:child_process')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '../..')
const URL = process.env.URL ?? 'http://127.0.0.1:8765/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `slides-${Date.now() % 100000}`
const ANN = ['ann', 'Ann has a password 1']
const log = (...a) => console.log(...a)

/** A workbook export: Sheet1 with four rows of sales, the slide "Sales chart" after it with a text box, and Costs. */
function seed() {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'claudia-e2e-slides-')), 'sales.claudia-export.zip')
  const python = `
import sys
from claudia_computes import AddSheet, AddSlide, SetCells, WorkbookModel
from claudia_core import AddObject, Document, MemoryStore, ObjectBody, SlideAnchor, paragraph_for
from claudia_document_file.export_file import write_export
doc = Document(WorkbookModel(), store=MemoryStore())
doc.execute(AddSheet("s1", "Sheet1"), author="ann")
rows = [("Region", "Sales"), ("East", 300), ("West", 120), ("North", 90)]
cells = tuple((r, c, {"t": "text", "v": v} if isinstance(v, str) else {"t": "int", "v": v}) for r, row in enumerate(rows) for c, v in enumerate(row))
doc.execute(SetCells("s1", cells), author="ann")
doc.execute(AddSlide("p1", "Sales chart"), author="ann")
doc.execute(AddSheet("s2", "Costs"), author="ann")
box = ObjectBody("t1", "text", 600, 160, "plain-box", paragraph_for("t1", "body-text", "East leads"), name="Note")
doc.execute(AddObject(box, SlideAnchor("p1", 160, 120).to_data()), author="ann")
data = write_export("computes", WorkbookModel.state_schema, doc.model.serialize(), exporter="ann", exported_at="2026-11-22T12:00:00Z")
open(sys.argv[1], "wb").write(data)
`
  execFileSync(path.join(ROOT, '.venv/bin/python'), ['-c', python, file], { cwd: ROOT, stdio: 'inherit' })
  return file
}

async function open(browser, file) {
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 860 } })).newPage()
  page.errors = []
  page.on('pageerror', (e) => page.errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && page.errors.push('console: ' + m.text()))
  await page.goto(URL)
  await page.setInputFiles('input[type=file]', file)
  await page.fill('.modal input >> nth=0', DOC)
  await page.locator('.modal input[autocomplete=username], .modal input[name=user]').first().fill(ANN[0])
  await page.locator('.modal input[type=password]').fill(ANN[1])
  await page.click('.modal button:text-is("Open")')
  await page.waitForSelector('[data-testid=recovery-key]', { timeout: 20000 })
  await page.check('.modal input[type=checkbox]')
  await page.click('.modal button:text-is("Continue")')
  await page.waitForSelector('.foot [role=tab]')
  await page.waitForFunction(() => document.querySelector('.health.open'))
  for (let i = 0; i < 3 && (await page.locator('.modal').count()); i++) await page.keyboard.press('Escape')
  return page
}
const tabs = (page) => page.$$eval('.foot [role=tablist] [role=tab]', (els) => els.map((e) => [e.dataset.kind, e.getAttribute('aria-label') ?? e.textContent.trim()]))
const statusIs = (page, re) => page.waitForFunction((src) => new RegExp(src).test(document.querySelector('[data-testid=print-status]')?.textContent ?? ''), re.source)
async function menu(page, title, ...items) {
  await page.click(`.menus .title:text-is("${title}")`)
  for (const item of items) await page.click(`.menus .drop [role=menuitem]:has-text("${item}")`)
}

;(async () => {
  fs.mkdirSync(SHOTS, { recursive: true })
  const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {})
  try {
    const page = await open(browser, seed())

    // ---- one list of tabs, the slide told apart from the sheets
    assert.deepEqual(await tabs(page), [['sheet', 'Sheet1'], ['slide', 'Slide: Sales chart'], ['sheet', 'Costs']])
    assert.ok(await page.locator('.formulaRow').isVisible(), 'a sheet has its formula bar')
    log('tabs: Sheet1, the slide Sales chart, Costs')

    // ---- the slide is shown with creates' view and tools: its text box, no formula bar, no Present
    await page.click('.foot [role=tab][data-kind=slide]')
    await page.waitForSelector('[data-testid=slide]')
    await page.waitForFunction(() => document.querySelector('[data-testid=slide]')?.textContent.includes('East leads'))
    assert.equal(await page.locator('.formulaRow').count(), 0, 'a slide has no cells, so no formula bar')
    assert.equal(await page.locator('[data-tool=present]').count(), 0, 'a workbook does not present its slides')
    assert.equal(await page.locator('.foot [role=tab][aria-selected=true]').getAttribute('data-kind'), 'slide')
    assert.equal(await page.locator('.obj.selected, .obj.on').count(), 0, 'a slide is shown with nothing selected')
    await page.screenshot({ path: `${SHOTS}/computes-slides-1-the-slide.png` })
    log('the slide shows its text box with the slide tools')

    // ---- a text box is put on it with the tool Text, and undo takes it away
    await page.click('[data-tool="text"]')
    await page.waitForFunction(() => document.querySelectorAll('[data-testid=slide] .obj.text').length === 2)
    await page.click('[data-testid=slide]', { position: { x: 5, y: 5 } })
    await page.keyboard.press('Control+z')
    await page.waitForFunction(() => document.querySelectorAll('[data-testid=slide] .obj.text').length === 1)
    log('a text box came with the tool Text and went with undo')

    // ---- File ▸ Print… prints the slide shown as one landscape page, and the workbook with the slide between the sheets
    await menu(page, 'File', 'Print')
    await page.waitForSelector('[data-testid=print-pages] .page svg')
    await statusIs(page, /1 page/)
    await statusIs(page, /landscape/)
    await page.screenshot({ path: `${SHOTS}/computes-slides-2-print-the-slide.png` })
    await page.selectOption('[data-testid=print-contents]', 'workbook')
    await statusIs(page, /^2 pages/)
    const sides = await page.$$eval('[data-testid=print-pages] .page svg', (els) => els.map((e) => { const b = e.viewBox.baseVal; return b.width > b.height ? 'landscape' : 'portrait' }))
    // Sheet1, then the slide; Costs has nothing on it, so it prints no page (as any empty sheet)
    assert.deepEqual(sides, ['portrait', 'landscape'], 'the slide is the second page, lying as a slide does')
    await page.screenshot({ path: `${SHOTS}/computes-slides-3-print-the-workbook.png` })
    await page.click('[data-testid=print-close]')
    log('print: the slide alone, and between the sheets of the workbook')

    // ---- back to a sheet: its grid and formula bar are back
    await page.click('.foot [role=tab]:has-text("Sheet1")')
    await page.waitForSelector('.formulaRow')
    assert.equal(await page.locator('[data-testid=slide]').count(), 0)

    assert.deepEqual(page.errors, [], 'no errors in the browser')
    log('ALL GOOD')
  } finally {
    await browser.close()
  }
})().catch((error) => {
  console.error(error)
  process.exit(1)
})
