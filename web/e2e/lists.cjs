// Lists in a text (E9.21), in real browser windows with two people (server: --model claudia_composes:TextModel).
// BROWSER=firefox runs it in Firefox (the owner's main browser); CHROME=/path/to/chrome uses a browser that is installed.
const { chromium, firefox } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8766/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `lists-${Date.now() % 100000}`
const ANN = ['ann', 'Ann has a password 1']
const BEN = ['ben', 'Ben has a password 1']
const log = (...a) => console.log(...a)

async function open(browser, [user, password], create) {
  const context = await browser.newContext({ viewport: { width: 1360, height: 800 } })
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

// What the person reads in each paragraph: the words (the marker is drawn by CSS and is no text) and the marker.
const readParagraphs = () =>
  [...document.querySelectorAll('[data-testid=text] [data-block]')].map((e) => {
    const copy = e.cloneNode(true)
    copy.querySelectorAll('[data-skip]').forEach((x) => x.remove())
    const content = getComputedStyle(e, '::before').content
    return { text: copy.textContent, marker: content === 'none' || content === 'normal' ? null : content.replace(/^"|"$/g, ''), pad: getComputedStyle(e).paddingLeft }
  })
const read = (page) => page.evaluate(readParagraphs)
async function expectRead(page, expected, what) {
  const deadline = Date.now() + 8000
  let got = []
  while (Date.now() < deadline) {
    got = (await read(page)).map((p) => [p.text, p.marker])
    if (JSON.stringify(got) === JSON.stringify(expected)) return
    await page.waitForTimeout(100)
  }
  throw new Error(`${what}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(got)}`)
}
async function menu(page, title, ...path) {
  await page.click(`.menus .title:text-is("${title}")`)
  for (const item of path) await page.click(`.menus .drop [role^=menuitem]:has-text("${item}")`)
}
const paragraph = (page, n) => page.locator('[data-testid=text] [data-block]').nth(n)

;(async () => {
  const type = process.env.BROWSER === 'firefox' ? firefox : chromium
  const browser = await type.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {})
  try {
    const ann = await open(browser, ANN, true)
    await ann.click('[data-testid=text]')
    await ann.keyboard.type('one')
    await ann.keyboard.press('Enter')
    await ann.keyboard.type('two')
    await ann.keyboard.press('Enter')
    await ann.keyboard.type('three')
    await ann.waitForTimeout(1200)
    await expectRead(ann, [['one', null], ['two', null], ['three', null]], 'three plain paragraphs')

    // ---- numbers for all three, from the style bar
    await ann.keyboard.press('Control+a')
    await ann.click('[data-testid=list-numbers]')
    await expectRead(ann, [['one', '1.'], ['two', '2.'], ['three', '3.']], 'numbered')
    log('numbers drawn, the words untouched')

    // ---- Tab moves an item in, Shift+Tab out; the count of the others follows
    await paragraph(ann, 1).click()
    await ann.keyboard.press('Tab')
    await expectRead(ann, [['one', '1.'], ['two', 'a.'], ['three', '2.']], 'two indented')
    const pads = (await read(ann)).map((p) => parseFloat(p.pad))
    assert.ok(pads[1] > pads[0], 'the indented item is moved in: ' + pads.join(', '))
    await ann.keyboard.press('Shift+Tab')
    await expectRead(ann, [['one', '1.'], ['two', '2.'], ['three', '3.']], 'two outdented')
    log('Tab and Shift+Tab')

    // ---- Enter at the end of an item makes the next item; Enter on the empty one leaves the list
    await paragraph(ann, 2).click()
    await ann.keyboard.press('End')
    await ann.keyboard.press('Enter')
    await expectRead(ann, [['one', '1.'], ['two', '2.'], ['three', '3.'], ['', '4.']], 'a fourth item')
    await ann.keyboard.press('Enter')
    await expectRead(ann, [['one', '1.'], ['two', '2.'], ['three', '3.'], ['', null]], 'out of the list')
    log('Enter continues, Enter on an empty item leaves')

    // ---- a second person sees the same, and writes while ann nests
    await menu(ann, 'File', 'Manage', 'Share')
    await ann.fill('.modal input >> nth=0', BEN[0])
    await ann.fill('.modal input >> nth=1', BEN[1])
    await ann.click('.modal button:has-text("Add person")')
    await ann.waitForSelector('.added')
    await ann.keyboard.press('Escape')
    const ben = await open(browser, BEN, false)
    await expectRead(ben, [['one', '1.'], ['two', '2.'], ['three', '3.'], ['', null]], 'ben sees the numbers')
    await paragraph(ben, 3).click()
    await ben.keyboard.type('Ben writes here')
    await paragraph(ann, 1).click()
    await ann.keyboard.press('Tab')
    const both = [['one', '1.'], ['two', 'a.'], ['three', '2.'], ['Ben writes here', null]]
    await expectRead(ann, both, 'ann after both')
    await expectRead(ben, both, 'ben after both')
    log('two writers converge on text and numbers')

    // ---- undo is exact: ann's indent goes, ben's words stay
    await paragraph(ann, 1).click()
    await ann.keyboard.press('Control+z')
    await expectRead(ben, [['one', '1.'], ['two', '2.'], ['three', '3.'], ['Ben writes here', null]], 'after ann undid')
    log('undo of the indent')

    // ---- the keys of the digits and the Format menu
    // (ben is still holding his paragraph: the server refuses ann there until he has moved on)
    await paragraph(ben, 0).click()
    await ben.waitForTimeout(1500)
    await paragraph(ann, 3).click()
    await ann.keyboard.press('End')
    await ann.waitForTimeout(300)
    await ann.keyboard.press('Control+Shift+8')
    await expectRead(ann, [['one', '1.'], ['two', '2.'], ['three', '3.'], ['Ben writes here', '•']], 'a bullet by key')
    await ann.keyboard.press('Control+Shift+8')
    await expectRead(ann, [['one', '1.'], ['two', '2.'], ['three', '3.'], ['Ben writes here', null]], 'the same key takes it out')
    await menu(ann, 'Format', 'List', 'Bulleted list')
    await expectRead(ann, [['one', '1.'], ['two', '2.'], ['three', '3.'], ['Ben writes here', '•']], 'a bullet by menu')
    await ann.screenshot({ path: `${SHOTS}/lists-ann.png` })
    log('Ctrl+Shift+8 and Format ▸ List')

    for (const page of [ann, ben]) assert.deepEqual(page.errors, [], 'no errors on the pages: ' + page.errors.join(' | '))
    log('OK')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error('FAILED:', e.message)
  process.exit(1)
})
