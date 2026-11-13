// File ▸ Print… in composes (D906): the pages are laid out in the browser by @claudia/layout, the page setup is the
// document's (D904), and the PDF the preview prints is the one it shows; the text is hyphenated by its language
// (D912, D915) (server: --model claudia_composes:TextModel with --fonts and --hyphenation). Run: URL=http://127.0.0.1:8766/ npm run e2e:print
const { chromium } = require('playwright')
const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const fs = require('node:fs')

const URL = process.env.URL ?? 'http://127.0.0.1:8766/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `report-${Date.now() % 100000}`
const ANN = ['ann', 'Ann has a password 1']
const VERA = ['vera', 'Vera has a password 1']
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
  await page.waitForSelector('[data-testid=text]')
  await page.waitForFunction(() => document.querySelector('.health.open'))
  return page
}
async function menu(page, title, ...path) {
  await page.click(`.menus .title:text-is("${title}")`)
  for (const item of path) await page.click(`.menus .drop [role=menuitem]:has-text("${item}")`)
}
const pageCount = (page) => page.$$eval('[data-testid=print-pages] .page', (els) => els.length)
async function download(page) {
  const [file] = await Promise.all([page.waitForEvent('download'), page.click('[data-testid=print-download]')])
  return fs.readFileSync(await file.path())
}

;(async () => {
  fs.mkdirSync(SHOTS, { recursive: true })
  const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {})
  try {
    const ann = await open(browser, ANN, true)
    await ann.click('[data-testid=text]')
    await ann.keyboard.type('Ein Bericht über Seiten')
    await ann.keyboard.press('Enter')
    const words = 'Eine Seite ist in Claudia keine Vermutung des Browsers mehr, sondern das Ergebnis einer Rechnung, die auf jedem Rechner dieselben Zahlen liefert. '
    for (let i = 0; i < 14; i++) {
      await ann.keyboard.type(words.repeat(3).trim())
      await ann.keyboard.press('Enter')
    }
    await ann.waitForTimeout(1500)
    await ann.click('[data-testid=text] [data-block]:first-child')
    await ann.click('[data-testid=style-button]')
    await ann.click('[data-style=title]')
    await ann.waitForTimeout(600)
    log('ann wrote a title and fourteen paragraphs')

    // ---- File ▸ Print… shows the pages in the window
    await menu(ann, 'File', 'Print')
    await ann.waitForSelector('[data-testid=print-pages] .page svg text')
    assert.ok((await pageCount(ann)) >= 2, 'more than one A4 page')
    assert.equal(await ann.locator('[data-testid=print-paper]').inputValue(), 'a4')
    assert.match(await ann.locator('[data-testid=print-status]').textContent(), /pages · A4 portrait/)
    assert.equal(await ann.locator('[data-testid=print-note]').count(), 0, 'every font of the built-in styles is on the server')
    await ann.waitForTimeout(500)
    await ann.screenshot({ path: `${SHOTS}/print-1-a4.png` })
    log('preview:', await pageCount(ann), 'A4 pages')

    // ---- the PDF: the same bytes twice, a real PDF with the text in it
    const pdf1 = await download(ann)
    const pdf2 = await download(ann)
    assert.equal(pdf1.subarray(0, 8).toString('latin1'), '%PDF-1.7')
    assert.equal(sha(pdf1), sha(pdf2), 'the same pages give the same PDF')
    log('PDF', pdf1.length, 'bytes, sha256', sha(pdf1).slice(0, 16))
    fs.writeFileSync(`${SHOTS}/print-a4.pdf`, pdf1)

    // ---- the page setup is the document's: Letter, landscape, page numbers
    const before = await pageCount(ann)
    await ann.selectOption('[data-testid=print-paper]', 'letter')
    await ann.waitForFunction(() => /Letter portrait/.test(document.querySelector('[data-testid=print-status]')?.textContent ?? ''))
    await ann.click('[data-testid=print-landscape]')
    await ann.waitForFunction(() => /Letter landscape/.test(document.querySelector('[data-testid=print-status]')?.textContent ?? ''))
    await ann.check('[data-testid=print-numbers]')
    await ann.waitForFunction(() => [...document.querySelectorAll('[data-testid=print-pages] .page:first-child text')].some((t) => t.textContent.trim() === '1 /'))
    const after = await pageCount(ann)
    assert.ok(after >= before, `landscape pages are lower: ${before} -> ${after}`)
    await ann.waitForTimeout(400)
    await ann.screenshot({ path: `${SHOTS}/print-2-letter-landscape.png` })
    log('Letter landscape with page numbers:', after, 'pages')
    // the history says what happened
    await ann.waitForFunction(() => [...document.querySelectorAll('aside')].some((a) => a.textContent.includes('set the page to Letter, landscape, page numbers')))

    // ---- a custom paper
    await ann.selectOption('[data-testid=print-paper]', 'custom')
    await ann.fill('[data-testid=print-custom] input >> nth=0', '100')
    await ann.fill('[data-testid=print-custom] input >> nth=1', '150')
    await ann.click('[data-testid=print-custom] button')
    await ann.waitForFunction(() => /100 × 150 mm landscape/.test(document.querySelector('[data-testid=print-status]')?.textContent ?? ''))
    log('custom paper 100 × 150 mm')

    // ---- the language of the text (D915): ann made it, so it started in her interface's language; in German the
    // narrow pages are hyphenated by the German patterns (D912), with no language not at all
    const lang = await ann.locator('[data-testid=print-language]').inputValue()
    assert.ok(/^en/.test(lang), `a new text starts in the creator's language, got ${lang}`)
    await ann.selectOption('[data-testid=print-language]', 'de')
    await ann.waitForFunction(() => [...document.querySelectorAll('aside')].some((a) => a.textContent.includes('set the language to de')))
    const hyphenated = () => [...document.querySelectorAll('[data-testid=print-pages] .page text')].filter((t) => /\p{L}-$/u.test(t.textContent)).length
    await ann.waitForFunction(hyphenated)
    log('German:', await ann.evaluate(hyphenated), 'lines end in a hyphen')
    await ann.waitForTimeout(400)
    await ann.screenshot({ path: `${SHOTS}/print-3-hyphenated.png` })
    await ann.selectOption('[data-testid=print-language]', '')
    await ann.waitForFunction(() => [...document.querySelectorAll('[data-testid=print-note]')].some((n) => n.textContent.includes('no language set')))
    assert.equal(await ann.evaluate(hyphenated), 0, 'no language, no hyphens')
    await ann.selectOption('[data-testid=print-language]', 'de')
    await ann.waitForFunction(hyphenated)
    log('no language: not hyphenated, and the preview says so')

    // ---- Ctrl+P prints the PDF Download gives (a headless browser cannot show a print dialog: the page hands the
    // PDF to a test hook instead of its print frame)
    await ann.evaluate(() => (window.__claudiaPrintDialog = (pdf) => (window.__printed = Array.from(pdf))))
    await ann.keyboard.press('Control+p')
    await ann.waitForFunction(() => window.__printed)
    const printed = Buffer.from(await ann.evaluate(() => window.__printed))
    const downloaded = await download(ann)
    fs.writeFileSync(`${SHOTS}/printed.pdf`, printed)
    fs.writeFileSync(`${SHOTS}/downloaded.pdf`, downloaded)
    assert.equal(sha(printed), sha(downloaded), 'what is printed is what is downloaded')
    log('Ctrl+P prints the same PDF as Download PDF')

    // ---- Esc goes back to the text
    await ann.keyboard.press('Escape')
    await ann.waitForSelector('[data-testid=text]')
    assert.equal(await ann.locator('[data-testid=print-preview]').count(), 0)

    // ---- Ctrl+- types a soft hyphen: where a word may be broken (D912)
    await ann.click('[data-testid=text] [data-block]:last-child')
    await ann.keyboard.press('End')
    await ann.keyboard.type(' Donau')
    await ann.keyboard.press('Control+Minus')
    await ann.keyboard.type('dampf')
    await ann.waitForFunction(() => document.querySelector('[data-testid=text] [data-block]:last-child')?.textContent.includes('Donau\u00addampf'))
    log('Ctrl+- typed a soft hyphen')

    // ---- a viewer sees the pages but cannot change the paper
    await menu(ann, 'File', 'Manage', 'Share')
    await ann.fill('.modal input >> nth=0', VERA[0])
    await ann.fill('.modal input >> nth=1', VERA[1])
    await ann.selectOption('.modal select', 'viewer').catch(() => {})
    await ann.click('.modal button:has-text("Add person")')
    await ann.waitForSelector('.added')
    await ann.keyboard.press('Escape')
    const vera = await open(browser, VERA, false)
    await vera.keyboard.press('Control+p')
    await vera.waitForSelector('[data-testid=print-pages] .page svg text')
    assert.ok(await vera.locator('[data-testid=print-paper]').isDisabled(), 'a viewer cannot change the paper')
    assert.ok(await vera.locator('[data-testid=print-language]').isDisabled(), 'nor the language')
    assert.equal(await vera.locator('[data-testid=print-language]').inputValue(), 'de')
    assert.match(await vera.locator('[data-testid=print-status]').textContent(), /100 × 150 mm landscape/, 'she sees the document’s page')
    log('vera sees the same pages and cannot change them')

    for (const p of [ann, vera]) assert.deepEqual(p.errors, [], p.errors.join('\n'))
    log('print preview: all checks passed')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error(e)
  process.exit(1)
})
