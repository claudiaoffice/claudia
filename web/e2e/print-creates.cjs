// File ▸ Print… in creates (D917, D918): the same preview as composes, with a Layout choice. Slides print one to a
// slide-sized page edge to edge, or as handouts of 2, 3 (with lines), 4, 6 or 9 to a page; how the presentation prints
// is the document's, a step in its history; the PDF printed is the one downloaded. Start a creates server with fonts
// and hyphenation first (scripts/start.py does). Run: URL=http://127.0.0.1:8767/ npm run e2e:print-creates
const { chromium } = require('playwright')
const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const fs = require('node:fs')

const URL = process.env.URL ?? 'http://127.0.0.1:8767/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `talk-${Date.now() % 100000}`
const ANN = ['ann', 'Ann has a password 1']
const BEN = ['ben', 'Ben has a password 1']
const log = (...a) => console.log(...a)
const sha = (b) => crypto.createHash('sha256').update(b).digest('hex')

async function open(browser, [user, password], create) {
  const context = await browser.newContext({ viewport: { width: 1360, height: 860 }, acceptDownloads: true })
  const page = await context.newPage()
  page.errors = []
  page.on('pageerror', (e) => page.errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && page.errors.push('console: ' + m.text()))
  await page.goto(URL)
  await page.fill('input[name=document]', DOC)
  await page.fill('input[name=user]', user)
  await page.fill('input[name=password]', password)
  await page.click(create ? 'text=Create document' : 'button:text-is("Open")')
  if (create) {
    await page.waitForSelector('[data-testid=recovery-key]')
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
  }
  await page.waitForSelector('[data-testid=slide]')
  await page.waitForFunction(() => document.querySelector('.health.open'))
  return page
}
async function menu(page, title, ...path) {
  await page.click(`.menus .title:text-is("${title}")`)
  for (const item of path) await page.click(`.menus .drop [role=menuitem]:has-text("${item}")`)
}
const status = (page) => page.locator('[data-testid=print-status]').textContent()
const statusIs = (page, re) => page.waitForFunction((src) => new RegExp(src).test(document.querySelector('[data-testid=print-status]')?.textContent ?? ''), re.source)
const pageCount = (page) => page.$$eval('[data-testid=print-pages] .page', (els) => els.length)
const history = (page, words) => page.waitForFunction((w) => [...document.querySelectorAll('aside')].some((a) => a.textContent.includes(w)), words)
async function download(page) {
  const [file] = await Promise.all([page.waitForEvent('download'), page.click('[data-testid=print-download]')])
  return fs.readFileSync(await file.path())
}
async function write(page, words) {
  const before = await page.locator('.obj.text').count()
  await page.click('[data-tool="text"]')
  await page.waitForFunction((n) => document.querySelectorAll('.obj.text').length === n + 1, before)
  const id = await page.locator('.obj.text').nth(before).getAttribute('data-id')
  await page.dblclick(`.obj[data-id="${id}"]`)
  await page.waitForSelector('textarea.editor')
  await page.keyboard.type(words)
  await page.keyboard.press('Enter')
  await page.waitForFunction(([i, w]) => document.querySelector(`.obj[data-id="${i}"]`)?.textContent.includes(w), [id, words])
}

;(async () => {
  fs.mkdirSync(SHOTS, { recursive: true })
  const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {})
  try {
    // ---- ann makes three slides: words and a shape on the first, words on the others
    const ann = await open(browser, ANN, true)
    await write(ann, 'Printing slides')
    await ann.click('[data-tool="rectangle"]')
    await ann.waitForFunction(() => document.querySelectorAll('.obj svg path').length === 1)
    for (const words of ['Handouts', 'With lines for notes']) {
      await ann.click('button[aria-label="new slide"]')
      await ann.waitForFunction((n) => document.querySelectorAll('[aria-label=slides] [role=tab]').length === n, words === 'Handouts' ? 2 : 3)
      await ann.waitForTimeout(300)
      await write(ann, words)
    }
    log('ann made three slides')

    // ---- File ▸ Print… shows the pages in place of the slide: one slide-sized page per slide, edge to edge
    await menu(ann, 'File', 'Print')
    await ann.waitForSelector('[data-testid=print-pages] .page svg text')
    assert.equal(await ann.locator('[data-testid=slide]').count(), 0, 'the preview is where the slide was')
    assert.equal(await ann.locator('[aria-label=insert]').count(), 0, 'and the insert bar is gone')
    assert.equal(await pageCount(ann), 3)
    assert.equal(await ann.locator('[data-testid=print-layout]').inputValue(), 'slides')
    assert.equal(await ann.locator('[data-testid=print-paper]').inputValue(), 'slide')
    assert.equal(await ann.locator('[data-testid=print-margins]').inputValue(), 'none')
    assert.match(await status(ann), /^3 slides on 3 pages · Slide size landscape$/)
    // the bar is composes' bar, control for control, with Layout in front
    const bar = await ann.$$eval('[data-testid=print-preview] [role=toolbar] [data-testid]', (els) => els.map((e) => e.dataset.testid))
    assert.deepEqual(bar, ['print-close', 'print-layout', 'print-paper', 'print-portrait', 'print-landscape', 'print-margins', 'print-language', 'print-numbers', 'print-download', 'print-print'])
    const lang = await ann.locator('[data-testid=print-language]').inputValue()
    assert.ok(/^en/.test(lang), `a new presentation starts in its maker's language, got ${lang}`)
    assert.equal(await ann.locator('[data-testid=print-note]').count(), 0, 'every font of the built-in styles is on the server')
    await ann.waitForTimeout(500)
    await ann.screenshot({ path: `${SHOTS}/print-creates-1-slides.png` })
    log('preview: 3 slide-sized pages')

    // ---- the PDF: the same bytes twice
    const pdf1 = await download(ann)
    const pdf2 = await download(ann)
    assert.equal(pdf1.subarray(0, 8).toString('latin1'), '%PDF-1.7')
    assert.equal(sha(pdf1), sha(pdf2), 'the same slides give the same PDF')
    fs.writeFileSync(`${SHOTS}/print-creates-slides.pdf`, pdf1)
    log('PDF', pdf1.length, 'bytes')

    // ---- handouts, 6 to a page: off the slide-sized paper, onto A4 portrait; one step in the history
    await ann.selectOption('[data-testid=print-layout]', 'handouts-6')
    await statusIs(ann, /^3 slides on 1 page · A4 portrait$/)
    assert.equal(await ann.locator('[data-testid=print-paper]').inputValue(), 'a4')
    assert.equal(await ann.locator('[data-testid=print-margins]').inputValue(), 'narrow')
    await history(ann, 'set printing to 6 slides a page on A4, portrait')
    await ann.waitForTimeout(400)
    await ann.screenshot({ path: `${SHOTS}/print-creates-2-handouts-6.png` })
    log('handouts: 6 a page on A4')

    // ---- 3 to a page with lines for notes, page numbers
    await ann.selectOption('[data-testid=print-layout]', 'handouts-3')
    await ann.check('[data-testid=print-numbers]')
    await ann.waitForFunction(() => [...document.querySelectorAll('[data-testid=print-pages] .page:first-child text')].some((t) => t.textContent.trim() === '1 /'))
    const rules = await ann.$$eval('[data-testid=print-pages] .page:first-child path', (els) => els.length)
    assert.ok(rules > 10, `ruled lines beside the slides: ${rules} paths`)
    await ann.waitForTimeout(400)
    await ann.screenshot({ path: `${SHOTS}/print-creates-3-handouts-3.png` })
    log('handouts: 3 a page with lines and page numbers')

    // ---- landscape, then back to slides on the slide-sized paper
    await ann.click('[data-testid=print-landscape]')
    await statusIs(ann, /A4 landscape$/)
    await ann.selectOption('[data-testid=print-layout]', 'slides')
    await statusIs(ann, /^3 slides on 3 pages · A4 landscape$/)
    await ann.selectOption('[data-testid=print-paper]', 'slide')
    await statusIs(ann, /^3 slides on 3 pages · Slide size landscape$/)
    assert.equal(await ann.locator('[data-testid=print-margins]').inputValue(), 'none')
    await ann.selectOption('[data-testid=print-layout]', 'handouts-4')
    await statusIs(ann, /^3 slides on 1 page · A4 portrait$/)

    // ---- Ctrl+P prints the PDF Download gives
    await ann.evaluate(() => (window.__claudiaPrintDialog = (pdf) => (window.__printed = Array.from(pdf))))
    await ann.keyboard.press('Control+p')
    await ann.waitForFunction(() => window.__printed)
    const printed = Buffer.from(await ann.evaluate(() => window.__printed))
    const downloaded = await download(ann)
    assert.equal(sha(printed), sha(downloaded), 'what is printed is what is downloaded')
    log('Ctrl+P prints the same PDF as Download PDF')

    // ---- Esc goes back to the slide
    await ann.keyboard.press('Escape')
    await ann.waitForSelector('[data-testid=slide]')
    assert.equal(await ann.locator('[data-testid=print-preview]').count(), 0)
    assert.equal(await ann.locator('[aria-label=slides] [role=tab]').count(), 3)

    // ---- a viewer sees the pages as the presentation prints, and cannot change them
    await menu(ann, 'File', 'Manage', 'Share')
    await ann.fill('.modal input >> nth=0', BEN[0])
    await ann.fill('.modal input >> nth=1', BEN[1])
    await ann.selectOption('.modal select', 'viewer').catch(() => {})
    await ann.click('.modal button:has-text("Add person")')
    await ann.waitForSelector('.added')
    await ann.keyboard.press('Escape')
    const ben = await open(browser, BEN, false)
    await ben.keyboard.press('Control+p')
    await ben.waitForSelector('[data-testid=print-pages] .page svg text')
    for (const control of ['layout', 'paper', 'margins', 'language']) assert.ok(await ben.locator(`[data-testid=print-${control}]`).isDisabled(), `a viewer cannot change the ${control}`)
    assert.equal(await ben.locator('[data-testid=print-layout]').inputValue(), 'handouts-4')
    assert.match(await status(ben), /^3 slides on 1 page · A4 portrait$/)
    log('ben sees the same pages and cannot change them')

    for (const p of [ann, ben]) assert.deepEqual(p.errors, [], p.errors.join('\n'))
    log('print preview (creates): all checks passed')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error(e)
  process.exit(1)
})
