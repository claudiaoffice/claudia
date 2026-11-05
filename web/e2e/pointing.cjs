// Pointing at cells with the mouse while typing a formula, in a real browser.
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8765/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `pointing-${Date.now() % 100000}`
const log = (...a) => console.log(...a)

async function cellAt(page, row, col) {
  const box = await page.locator('.viewport').boundingBox()
  return { x: box.x + 52 + col * 96 + 40, y: box.y + 26 + row * 26 + 13 }
}
async function click(page, row, col) {
  const p = await cellAt(page, row, col)
  await page.mouse.click(p.x, p.y)
}
async function drag(page, from, to) {
  const a = await cellAt(page, ...from)
  const b = await cellAt(page, ...to)
  await page.mouse.move(a.x, a.y)
  await page.mouse.down()
  await page.mouse.move(b.x, b.y, { steps: 6 })
  await page.mouse.up()
}
const editor = (page) => page.locator('input.editor').inputValue()
const bar = (page) => page.locator('input[aria-label="cell content"]').inputValue()
async function text(page, row, col) {
  const p = await cellAt(page, row, col)
  return page.evaluate(({ x, y }) => {
    const box = document.querySelector('.stage').getBoundingClientRect()
    const left = x - box.left - 40 - 0
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
    await page.waitForTimeout(100)
  }
  throw new Error(`cell ${row},${col} is ${JSON.stringify(await text(page, row, col))}, not ${expected}`)
}
async function type(page, row, col, input) {
  await click(page, row, col)
  await page.keyboard.type(input)
  await page.keyboard.press('Enter')
}

;(async () => {
  const browser = await chromium.launch()
  const context = await browser.newContext({ viewport: { width: 1360, height: 800 } })
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
    // a new document first shows its recovery key; the person must confirm having stored it
    await page.waitForSelector('[data-testid=recovery-key]')
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
    await page.waitForSelector('.viewport')
    await page.waitForFunction(() => document.querySelector('.status.open'))

    for (const [i, n] of [1, 2, 3, 4].entries()) await type(page, i, 0, String(n)) // A1:A4
    for (const [i, n] of [10, 20, 30, 40].entries()) await type(page, i, 1, String(n)) // B1:B4
    await waitCell(page, 3, 1, '40')

    // 1. the first argument: =SUM( then drag over A1:A4
    await click(page, 0, 3)
    await page.keyboard.type('=SUM(')
    await drag(page, [0, 0], [3, 0])
    assert.equal(await editor(page), '=SUM(A1:A4')
    assert.equal(await bar(page), '=SUM(A1:A4', 'the formula bar shows it too')
    await page.screenshot({ path: `${SHOTS}/p1-pointing.png` })
    await page.keyboard.type(')') // the focus stayed in the text
    await page.keyboard.press('Enter')
    await waitCell(page, 0, 3, '10')
    log('SUM over a dragged range: ok')

    // 2. any argument: the third one of SUMIF
    await click(page, 1, 3)
    await page.keyboard.type('=SUMIF(')
    await drag(page, [0, 0], [3, 0])
    await page.keyboard.type(',">2",')
    await drag(page, [0, 1], [3, 1])
    assert.equal(await editor(page), '=SUMIF(A1:A4,">2",B1:B4')
    await page.keyboard.type(')')
    await page.keyboard.press('Enter')
    await waitCell(page, 1, 3, '70')
    log('third argument: ok')

    // 3. a second click replaces the first pick; the formula keeps its operators
    await click(page, 2, 3)
    await page.keyboard.type('=A1+')
    await click(page, 0, 1)
    assert.equal(await editor(page), '=A1+B1')
    await click(page, 1, 1)
    assert.equal(await editor(page), '=A1+B2', 'a second click replaces the first')
    await page.keyboard.press('Enter')
    await waitCell(page, 2, 3, '21')
    log('replacing a pick: ok')

    // 4. between brackets: the text after the caret stays
    await click(page, 3, 3)
    await page.keyboard.type('=SUM()+1')
    for (let i = 0; i < 3; i++) await page.keyboard.press('ArrowLeft')
    await drag(page, [0, 0], [1, 0])
    assert.equal(await editor(page), '=SUM(A1:A2)+1')
    await page.keyboard.press('Enter')
    await waitCell(page, 3, 3, '4')
    log('between brackets: ok')

    // 5. a whole column from its header
    await click(page, 4, 3)
    await page.keyboard.type('=SUM(')
    const head = await page.locator('.viewport').boundingBox()
    await page.mouse.click(head.x + 52 + 1 * 96 + 40, head.y + 13) // the header of B
    assert.equal(await editor(page), '=SUM(B:B')
    await page.keyboard.type(')')
    await page.keyboard.press('Enter')
    await waitCell(page, 4, 3, '100')
    log('whole column: ok')

    // 6. where no reference fits, a click ends the edit as before
    await click(page, 5, 3)
    await page.keyboard.type('=1')
    await click(page, 0, 0)
    await waitCell(page, 5, 3, '1')
    log('a click after a number keeps the edit: ok')

    // 7. text is never picked into
    await click(page, 6, 3)
    await page.keyboard.type('="a,')
    await click(page, 0, 0)
    await waitCell(page, 6, 3, '#ERROR!') // (the click ended the edit: an unfinished text is a formula that does not parse)
    assert.equal(await page.locator('input.editor').count(), 0)
    log('a click inside a text keeps the edit: ok')

    // 8. another sheet
    await page.click('button[aria-label="new sheet"]')
    await page.fill('.modal input', 'Other data')
    await page.click('.modal button:has-text("Add sheet")')
    await page.waitForSelector('.tab.on:has-text("Other data"), [role=tab].on:has-text("Other data")')
    await type(page, 0, 0, '5')
    await page.click('[role=tab]:has-text("Sheet1")')
    await click(page, 7, 3)
    await page.keyboard.type('=')
    await page.click('[role=tab]:has-text("Other data")')
    await click(page, 0, 0)
    assert.equal(await bar(page), "='Other data'!A1")
    await page.screenshot({ path: `${SHOTS}/p2-other-sheet.png` })
    await page.keyboard.press('Enter')
    await page.waitForSelector('[role=tab].on:has-text("Sheet1")')
    await waitCell(page, 7, 3, '5')
    log('another sheet: ok')

    // 9. the references of a formula are outlined while it is edited
    await click(page, 8, 3)
    await page.keyboard.type('=A1+B2')
    assert.equal(await page.locator('.reference').count(), 2)
    await page.screenshot({ path: `${SHOTS}/p3-outlines.png` })
    await page.keyboard.press('Escape')
    assert.equal(await page.locator('.reference').count(), 0)
    log('outlines: ok')

    assert.deepEqual(errors, [], 'no errors in the browser: ' + errors.join(' | '))
    log('all ok')
  } catch (e) {
    await page.screenshot({ path: `${SHOTS}/p-failure.png` }).catch(() => undefined)
    console.error('FAILED:', e.message, errors)
    process.exitCode = 1
  } finally {
    await browser.close()
  }
})()
