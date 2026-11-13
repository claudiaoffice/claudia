// Keyboard access to the parts of a document window, in a real browser (BITV 2.0: 2.1.2 no keyboard trap, 2.4.1 bypass
// blocks, 2.4.2 page titled, 3.1.1 language of the page). In computes the grid keeps Tab for stepping between cells, so
// F6 and Shift+F6 are the way out; they must work from the formula bar too, and wrap round at both ends.
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8765/'
const DOC = `regions-${Date.now() % 100000}`
const log = (...a) => console.log(...a)

/** Which marked part of the window holds focus now ('' when none does). */
const regionOfFocus = (page) =>
  page.evaluate(() => document.activeElement?.closest('[data-region]')?.getAttribute('data-region') ?? '')

async function open(page) {
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
}

;(async () => {
  const browser = await chromium.launch()
  const context = await browser.newContext({ viewport: { width: 1360, height: 800 }, locale: 'en-US' })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push('console: ' + m.text()))
  try {
    await open(page)

    // 2.4.2 and 3.1.1
    assert.equal(await page.title(), `${DOC} – Claudia Computes`, 'the tab names the document and the app')
    assert.equal(await page.evaluate(() => document.documentElement.lang), 'en', 'the page declares its language')
    log('title and language: ok')

    // Tab still steps between cells, and stays in the grid
    await page.click('.viewport', { position: { x: 100, y: 40 } })
    await page.keyboard.press('Tab')
    assert.equal(await regionOfFocus(page), 'document', 'Tab in the grid stays in the grid')

    // 2.1.2: F6 leaves the grid, and goes round the window
    const seen = []
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('F6')
      seen.push(await regionOfFocus(page))
    }
    assert.deepEqual(seen, ['panel', 'footer', 'menus', 'toolbar', 'document'], `F6 order was ${seen}`)
    log('F6 goes round the window: ok')

    // and backwards
    await page.keyboard.press('Shift+F6')
    assert.equal(await regionOfFocus(page), 'toolbar')
    await page.keyboard.press('Shift+F6')
    assert.equal(await regionOfFocus(page), 'menus')
    log('Shift+F6 goes back: ok')

    // from inside a text field: the formula bar
    // (the first click starts editing the cell, which hands focus to the cell's own editor; the second lands in the bar)
    await page.click('input[aria-label="cell content"]')
    await page.click('input[aria-label="cell content"]')
    assert.equal(await regionOfFocus(page), 'toolbar')
    await page.keyboard.press('F6')
    assert.equal(await regionOfFocus(page), 'document', 'F6 leaves the formula bar')
    log('F6 from the formula bar: ok')

    // a closed panel is skipped
    await page.click('button.panel:has-text("History")')
    await page.focus('.viewport')
    await page.keyboard.press('F6')
    assert.equal(await regionOfFocus(page), 'footer', 'a hidden panel is passed over')
    log('hidden panel skipped: ok')

    assert.deepEqual(errors, [], 'no console errors')
    log('regions: all ok')
  } catch (e) {
    await page.screenshot({ path: `${process.env.SHOTS ?? '/tmp'}/regions-failed.png` }).catch(() => {})
    console.error(e)
    process.exitCode = 1
  } finally {
    await browser.close()
  }
})()
