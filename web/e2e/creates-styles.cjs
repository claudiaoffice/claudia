// Styles on slides, in a real browser (owner's report, 2026-11-12: "I re-styled a text box, named the style, and could
// not apply it to another one"). Start a presentation server first:
//   uv run python scripts/start.py creates --no-browser      (URL defaults to http://127.0.0.1:8765/)
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8765/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `deck-styles-${Date.now() % 100000}`
const log = (...a) => console.log(...a)

async function waitFor(page, fn, arg, what) {
  try {
    await page.waitForFunction(fn, arg, { timeout: 8000 })
  } catch {
    throw new Error('timed out waiting for ' + what)
  }
}

/** The look of an object's words (text box or shape label) and of its outline. */
const look = (page, id) =>
  page.$eval(`.obj[data-id="${id}"]`, (el) => {
    const words = getComputedStyle(el.querySelector('.text') ?? el)
    const path = el.querySelector('svg path')
    return { weight: words.fontWeight, fill: path ? getComputedStyle(path).fill : null }
  })

async function add(page, tool, kind) {
  const before = await page.$$eval(`.obj.${kind}`, (els) => els.map((e) => e.dataset.id))
  await page.click(`[data-tool="${tool}"]`)
  await waitFor(page, ([k, n]) => document.querySelectorAll(`.obj.${k}`).length === n, [kind, before.length + 1], tool)
  return page.$$eval(`.obj.${kind}`, (els, old) => els.map((e) => e.dataset.id).find((id) => !old.includes(id)), before)
}

/** Drag an object down by `dy` pixels (new objects land on the same place). */
async function moveDown(page, id, dy) {
  const b = await page.locator(`.obj[data-id="${id}"]`).boundingBox()
  await page.mouse.move(b.x + 8, b.y + 8)
  await page.mouse.down()
  await page.mouse.move(b.x + 8, b.y + 8 + dy, { steps: 6 })
  await page.mouse.up()
  await page.waitForTimeout(300)
}

const select = (page, id) => page.click(`.obj[data-id="${id}"]`, { position: { x: 6, y: 6 } })

async function write(page, id, words) {
  await page.dblclick(`.obj[data-id="${id}"]`, { position: { x: 30, y: 30 } })
  await page.waitForSelector('textarea.editor')
  await page.keyboard.type(words)
  await page.keyboard.press('Enter')
  await waitFor(page, ([i, w]) => document.querySelector(`.obj[data-id="${i}"]`)?.textContent.includes(w), [id, words], 'the words')
}

;(async () => {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1360, height: 860 } })
  const errors = []
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push('console: ' + m.text()))
  try {
    await page.goto(URL)
    await page.fill('input[name=document]', DOC)
    await page.fill('input[name=user]', 'ann')
    await page.fill('input[name=password]', 'Ann has a password 1')
    await page.click('text=Create document')
    await page.waitForSelector('[data-testid=recovery-key]')
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
    await page.waitForSelector('[data-testid=slide]')
    await page.waitForFunction(() => document.querySelector('.health.open'))

    // ---- two text boxes
    const first = await add(page, 'text', 'text')
    await write(page, first, 'First box')
    const second = await add(page, 'text', 'text')
    await write(page, second, 'Second box')
    await moveDown(page, second, 220)
    assert.equal(await page.locator('[data-testid=style-picker]').innerText().then((t) => t.replace('▾', '').trim()), 'Body text')
    log('the bar shows the selected text box style: Body text')

    // ---- the first one gets bolder words, only for itself, and the new style a name
    await select(page, first)
    await page.click('.menus .title:text-is("Format")')
    await page.click('.menus .drop [role=menuitem]:has-text("Edit This Style")')
    await page.waitForSelector('[data-testid=style-menu]')
    await page.locator('[data-testid=style-spec] input[value=new]').check()
    await page.click('[data-testid=bold]')
    await waitFor(page, (id) => getComputedStyle(document.querySelector(`.obj[data-id="${id}"] .text`)).fontWeight === '700', first, 'bold words')
    await page.fill('[data-testid=name-invitation] input', 'Callout')
    await page.click('[data-testid=name-invitation] button[type=submit]')
    await page.waitForSelector('[data-testid=name-invitation]', { state: 'detached' })
    await page.keyboard.press('Escape')
    assert.equal((await look(page, second)).weight, '400', 'the other box is untouched')
    log('restyled the first box and named its style “Callout”')

    // ---- the reported case: the named style onto the other, existing text box, from the bar
    await select(page, second)
    await page.click('[data-testid=style-picker]')
    await page.click('.list [data-style]:has-text("Callout")')
    await waitFor(page, (id) => getComputedStyle(document.querySelector(`.obj[data-id="${id}"] .text`)).fontWeight === '700', second, 'Callout on the second box')
    assert.match(await page.locator('[data-testid=style-picker]').innerText(), /Callout/)
    await page.screenshot({ path: `${SHOTS}/creates-styles-1.png` })
    log('applied “Callout” to the second box from the bar')

    // ---- a shape: its outline and its label each have their picker
    const rect = await add(page, 'rectangle', 'shape')
    await moveDown(page, rect, 420)
    await write(page, rect, 'Label')
    await select(page, rect)
    assert.match(await page.locator('[data-testid=style-picker]').innerText(), /Plain shape/)
    assert.match(await page.locator('[data-testid=label-picker]').innerText(), /Shape label/)
    await page.click('[data-testid=label-picker]')
    await page.click('.list [data-style]:has-text("Callout")')
    await waitFor(page, (id) => getComputedStyle(document.querySelector(`.obj[data-id="${id}"] .text`)).fontWeight === '700', rect, 'Callout on the label')
    assert.match(await page.locator('[data-testid=style-picker]').innerText(), /Plain shape/, 'the outline keeps its style')
    log('a shape has two pickers: outline “Plain shape”, label now “Callout”')

    // ---- with a text box selected there is no label picker; with nothing selected the picker is off
    await select(page, first)
    assert.equal(await page.locator('[data-testid=label-picker]').count(), 0)
    await page.click('[data-testid=slide]', { position: { x: 900, y: 40 } })
    await waitFor(page, () => document.querySelector('[data-testid=style-picker]').disabled, null, 'the picker off without a selection')

    // ---- All styles… counts objects, whatever is selected (it said "1 shape" beside Body text)
    await select(page, rect)
    await page.click('.menus .title:text-is("Format")')
    await page.click('.menus .drop [role=menuitem]:has-text("All Styles")')
    const rows = await page.$$eval('.modal li', (els) => els.map((e) => e.textContent.replace(/\s+/g, ' ').trim()))
    assert.ok(rows.some((r) => r.startsWith('Callout') && r.includes('3 objects')), rows.join(' | '))
    assert.ok(!rows.some((r) => /\d shapes?\b/.test(r)), 'no count names one kind for all: ' + rows.join(' | '))
    await page.screenshot({ path: `${SHOTS}/creates-styles-2.png` })
    await page.keyboard.press('Escape')
    log('All styles counts objects: Callout used by 3')

    assert.deepEqual(errors, [])
    console.log('\nALL GOOD')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error('FAILED:', e)
  process.exit(1)
})
