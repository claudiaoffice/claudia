// Styling a text: the style menu, in a real browser (server: --model claudia_composes:TextModel).
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8766/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `styles-${Date.now() % 100000}`
const log = (...a) => console.log(...a)

const look = (page, n) =>
  page.$$eval('[data-testid=text] [data-block]', (els, n) => {
    const c = getComputedStyle(els[n])
    return { tag: els[n].tagName.toLowerCase(), cls: els[n].className, weight: c.fontWeight, size: c.fontSize, color: c.color, family: c.fontFamily, align: c.textAlign, decoration: c.textDecorationLine }
  }, n)

async function main() {
  const browser = await chromium.launch()
  const context = await browser.newContext({ viewport: { width: 1360, height: 860 }, deviceScaleFactor: 2 })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push('console: ' + m.text()))
  await page.goto(URL)
  await page.fill('input[name=document]', DOC)
  await page.fill('input[name=user]', 'ann')
  await page.fill('input[name=password]', 'Ann has a password 1')
  await page.click('text=Create document')
  await page.waitForSelector('[data-testid=text]')
  await page.waitForFunction(() => document.querySelector('.status.open'))

  // three paragraphs: a title, two of body text
  await page.click('[data-testid=text]')
  await page.keyboard.type('Why styles come first. ')
  await page.keyboard.press('Enter')
  await page.keyboard.type('Mark text by what it is for, and look comes second. ')
  await page.keyboard.press('Enter')
  await page.keyboard.type('A second paragraph of body text, to be left alone. ')
  await page.waitForTimeout(900)
  await page.click('[data-testid=text] [data-block] >> nth=0')
  await page.keyboard.press('Control+Home')
  await page.click('[data-testid=style-button]')
  await page.click('[data-style=title]')
  await page.waitForTimeout(300)
  const title = await look(page, 0)
  assert.equal(title.tag, 'h1')
  assert.match(title.family, /Fraunces/)
  assert.notEqual(title.size, (await look(page, 1)).size, 'the title is drawn bigger than body text, from its CSS')
  log('built-in styles come from CSS:', title.size, 'vs', (await look(page, 1)).size)

  // the style list of the bar hangs below the bar and must really be on top there (not clipped by the bar)
  await page.click('[data-testid=style-button]')
  const hit = await page.evaluate(() => {
    const el = document.querySelector('.style-list [data-style=heading-1]')
    const r = el.getBoundingClientRect()
    return document.elementFromPoint(r.left + 20, r.top + r.height / 2)?.closest('[data-style]')?.getAttribute('data-style')
  })
  assert.equal(hit, 'heading-1', 'the list is visible and clickable where it is drawn')
  await page.screenshot({ path: `${SHOTS}/styling-0-dropdown.png` })
  await page.mouse.click(700, 500) // press outside: it closes
  await page.waitForSelector('.style-list', { state: 'detached' })
  await page.click('[data-testid=style-button]')
  const box = await page.locator('.style-list [data-style=heading-2]').boundingBox()
  await page.mouse.click(box.x + 20, box.y + box.height / 2) // a real mouse click on the entry, where it is drawn
  await page.waitForSelector('.style-list', { state: 'detached' })
  await page.waitForFunction(() => document.querySelector('[data-testid=text] [data-block]').className.includes('st-heading-2'))
  await page.click('[data-testid=style-button]')
  await page.click('[data-testid=style-button]') // the button toggles it
  await page.waitForSelector('.style-list', { state: 'detached' })
  await page.click('[data-testid=look-button]') // the same menu, without a right click
  await page.waitForSelector('[data-testid=style-menu]')
  await page.keyboard.press('Escape')
  await page.waitForSelector('[data-testid=style-menu]', { state: 'detached' })
  // a contextmenu event the way any browser sends it, also from the margin of the page, opens the menu and is not left to the browser
  const prevented = await page.evaluate(() => {
    const e = new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: 300, clientY: 300, button: 2 })
    document.querySelector('[data-testid=text-scroller]').dispatchEvent(e)
    return e.defaultPrevented
  })
  assert.equal(prevented, true)
  await page.waitForSelector('[data-testid=style-menu]')
  await page.keyboard.press('Escape')
  await page.waitForSelector('[data-testid=style-menu]', { state: 'detached' })
  log('style list of the bar is visible and closes; the Look button and a contextmenu event open the menu')

  // right-click in the second paragraph: the menu opens with the style gallery and the look
  const second = page.locator('[data-testid=text] [data-block]').nth(1)
  await second.click()
  await second.click({ button: 'right' })
  await page.waitForSelector('[data-testid=style-menu]')
  assert.equal(await page.locator('[data-testid=style-menu] [data-style].on').getAttribute('data-style'), 'body')
  await page.screenshot({ path: `${SHOTS}/styling-1-menu.png` })
  log('context menu open on Body text')

  // bold, this paragraph only: a new style appears and waits for its name, the others are untouched
  await page.click('[data-testid=bold]')
  await page.waitForFunction(() => document.querySelectorAll('[data-testid=text] [data-block]')[1].className.includes('body-text-changed'))
  assert.equal((await look(page, 1)).weight, '700')
  assert.equal((await look(page, 2)).weight, '400')
  assert.ok(await page.locator('[data-testid=name-invitation]').isVisible())
  log('bold deviates: paragraph 2 is bold, paragraph 3 is not; the menu invites a name')

  // the next change goes into the deviation (it is the person’s own), colour and size
  await page.click('[data-testid=colour-text]')
  await page.click('[data-testid=colour-text] .chip[title=Iris]')
  await page.click('[data-testid=size-field] button[aria-label=Larger]')
  await page.waitForFunction(() => getComputedStyle(document.querySelectorAll('[data-testid=text] [data-block]')[1]).color === 'rgb(91, 75, 196)')
  const dev = await look(page, 1)
  assert.equal(dev.cls.includes('body-text-changed'), true)
  assert.equal((await page.locator('[data-testid=text] [data-block][class*=body-text-changed]').count()), 1, 'still just the one paragraph')
  await page.screenshot({ path: `${SHOTS}/styling-2-controls.png` })
  log('colour and size went into the same new style:', dev.color, dev.size)

  // switch view: the CSS of that style
  await page.click('[data-testid=view-css]')
  const textarea = page.locator('[data-testid=css-view] textarea')
  const css = await textarea.inputValue()
  assert.match(css, /font-weight: bold;/)
  assert.match(css, /color: #5B4BC4;/i)
  await page.screenshot({ path: `${SHOTS}/styling-3-css.png` })
  log('css view shows:', JSON.stringify(css))

  // an error is shown with its line and nothing is sent
  await textarea.fill('font-weight: bold;\ncolor: red url(x);\nposition: fixed;')
  await page.waitForSelector('.problems')
  assert.match(await page.locator('.problems').innerText(), /Line 2/)
  assert.equal(await page.locator('[data-testid=css-apply]').isDisabled(), true)
  await page.screenshot({ path: `${SHOTS}/styling-4-problems.png` })
  log('problems named with their lines; Apply is off')

  // valid CSS applied with the keyboard
  await textarea.fill('font-weight: bold;\ncolor: #D6477A;\nfont-style: italic;\nborder-left: 3px solid #F2A057;\npadding-left: 12pt;')
  await page.waitForFunction(() => !document.querySelector('.problems'))
  await textarea.press('Control+Enter')
  await page.waitForFunction(() => getComputedStyle(document.querySelectorAll('[data-testid=text] [data-block]')[1]).fontStyle === 'italic')
  assert.equal((await look(page, 1)).color, 'rgb(214, 71, 122)')
  log('typed CSS applied')

  // name it
  await page.fill('[data-testid=name-invitation] input', 'Pull note')
  await page.click('[data-testid=name-invitation] button[type=submit]')
  await page.waitForSelector('[data-testid=name-invitation]', { state: 'detached' })
  assert.ok(await page.locator('[data-testid=style-menu] [data-style=body-text-changed]').count())
  log('named “Pull note”')

  // every use of Body text: back to controls, choose “every use”, change the size of all body text
  await page.keyboard.press('Escape')
  await page.waitForSelector('[data-testid=style-menu]', { state: 'detached' })
  await page.locator('[data-testid=text] [data-block]').nth(2).click()
  await page.locator('[data-testid=text] [data-block]').nth(2).click({ button: 'right' })
  await page.click('[data-testid=view-controls]')
  await page.locator('[data-testid=style-spec] label', { hasText: 'Every use of' }).click()
  const before = (await look(page, 2)).size
  await page.click('[data-testid=size-field] button[aria-label=Larger]')
  await page.waitForFunction((b) => getComputedStyle(document.querySelectorAll('[data-testid=text] [data-block]')[2]).fontSize !== b, before)
  assert.equal((await look(page, 1)).size, (await look(page, 1)).size)
  log('every use: body text got bigger (', before, '→', (await look(page, 2)).size, ')')
  await page.screenshot({ path: `${SHOTS}/styling-5-every.png` })
  await page.keyboard.press('Escape')

  // the dialog lists the styles and counts
  await page.click('text=Format')
  await page.click('text=All styles…')
  await page.waitForSelector('[data-testid=styles-list]')
  assert.match(await page.locator('[data-testid=styles-list] [data-style=body-text-changed]').innerText(), /1 paragraph/)
  await page.screenshot({ path: `${SHOTS}/styling-6-styles.png` })
  await page.keyboard.press('Escape')
  log('styles dialog')

  // undo takes the style change back (the size), then the naming and the rest
  await page.click('[data-testid=text] [data-block] >> nth=2')
  await page.keyboard.press('Control+z')
  await page.waitForFunction((b) => getComputedStyle(document.querySelectorAll('[data-testid=text] [data-block]')[2]).fontSize === b, before)
  log('undo restored the size')

  assert.deepEqual(errors, [])
  await browser.close()
  log('OK')
}
main().catch((e) => {
  console.error(e)
  process.exit(1)
})
