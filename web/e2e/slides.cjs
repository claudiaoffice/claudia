// Two people on one slide, in two real browser windows: put a text box and shapes on it, move, resize, edit and delete
// them, and see what the other holds. Start a presentation server first:
//   uv run python scripts/start.py --app creates --no-browser   (or: python -m claudia_server --model claudia_creates:SlideModel ...)
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8765/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `slides-${Date.now() % 100000}`
const ANN = ['ann', 'Ann has a password 1']
const BEN = ['ben', 'Ben has a password 1']

const log = (...a) => console.log(...a)
// The shapes are put on top of each other, a little shifted: these points of the first two are not covered by a later one.
const CORNER = { x: 8, y: 8 }
const TOP_OF_CIRCLE = { x: 60, y: 6 }

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
  await page.waitForSelector('[data-testid=slide]')
  await page.waitForFunction(() => document.querySelector('.status.open'))
  return page
}

async function waitFor(page, fn, arg, what) {
  try {
    await page.waitForFunction(fn, arg, { timeout: 8000 })
  } catch {
    throw new Error('timed out waiting for ' + what)
  }
}

const objects = (page) => page.$$eval('.obj', (els) => els.map((e) => ({ id: e.dataset.id, cls: e.className, text: e.textContent.trim(), label: e.getAttribute('aria-label') })))
const tool = (page, name) => page.click(`[data-tool="${name}"]`)
const box = (page, id) => page.locator(`.obj[data-id="${id}"]`).boundingBox()
async function slideBox(page) {
  return page.locator('[data-testid=slide]').boundingBox()
}
/** The frame of an object in slide units, read from the page (1600 units across the slide). */
async function frame(page, id) {
  const [s, b] = [await slideBox(page), await box(page, id)]
  const k = 1600 / s.width
  return { x: Math.round((b.x - s.x) * k), y: Math.round((b.y - s.y) * k), w: Math.round(b.width * k), h: Math.round(b.height * k) }
}
async function drag(page, from, to) {
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move((from.x + to.x) / 2, (from.y + to.y) / 2, { steps: 4 })
  await page.mouse.move(to.x, to.y, { steps: 4 })
  await page.mouse.up()
}
const centre = (b) => ({ x: b.x + b.width / 2, y: b.y + b.height / 2 })

;(async () => {
  const browser = await chromium.launch()
  try {
    // ---- ann makes a presentation: one empty slide
    const ann = await open(browser, ANN, true)
    assert.equal(await ann.locator('.doc').textContent(), DOC)
    assert.equal((await objects(ann)).length, 0)
    assert.equal(await ann.locator('.tabs [role=tab]').count(), 1)
    log('ann created', DOC, 'with one empty slide')

    // ---- a text box: added, selected, written into
    await tool(ann, 'text')
    await waitFor(ann, () => document.querySelectorAll('.obj.text').length === 1, null, 'the text box')
    const text = (await objects(ann))[0]
    assert.ok(text.cls.includes('selected'), 'a new object is selected')
    await ann.dblclick(`.obj[data-id="${text.id}"]`)
    await ann.waitForSelector('textarea.editor')
    await ann.keyboard.type('Hello slide')
    await ann.keyboard.press('Enter')
    await waitFor(ann, (id) => document.querySelector(`.obj[data-id="${id}"]`)?.textContent.includes('Hello slide'), text.id, 'the text to arrive')
    log('text written:', (await objects(ann))[0].text)

    // ---- moved by dragging
    const before = await frame(ann, text.id)
    const b0 = await box(ann, text.id)
    await drag(ann, { x: b0.x + 30, y: b0.y + 30 }, { x: b0.x + 30 + 200, y: b0.y + 30 + 120 })
    await waitFor(ann, () => true, null, 'the drag')
    await ann.waitForTimeout(300)
    const after = await frame(ann, text.id)
    assert.ok(Math.abs(after.x - before.x - 200 * (1600 / (await slideBox(ann)).width)) < 12, `moved right: ${before.x} -> ${after.x}`)
    assert.ok(after.y > before.y + 100, `moved down: ${before.y} -> ${after.y}`)
    assert.equal(after.w, before.w, 'moving does not resize')
    log('moved', before, '->', after)

    // ---- shapes: rectangle, circle, triangle
    for (const shape of ['rectangle', 'circle', 'triangle']) {
      await tool(ann, shape)
      await ann.waitForTimeout(150)
    }
    await waitFor(ann, () => document.querySelectorAll('.obj svg path').length === 3, null, 'three shapes')
    const shapes = (await objects(ann)).filter((o) => o.cls.includes('shape'))
    assert.equal(shapes.length, 3)
    assert.deepEqual(shapes.map((s) => s.label), ['Rectangle', 'Circle', 'Triangle'])

    // ---- the circle keeps its proportions when resized from a corner
    const circle = shapes[1]
    await ann.click(`.obj[data-id="${circle.id}"]`, { position: TOP_OF_CIRCLE })
    await ann.waitForSelector('.mine .handle[data-handle=se]')
    assert.equal(await ann.locator('.mine .handle').count(), 4, 'a circle can only be resized from its corners')
    const c0 = await frame(ann, circle.id)
    const h = await ann.locator('.mine .handle[data-handle=se]').boundingBox()
    await drag(ann, centre(h), { x: centre(h).x + 60, y: centre(h).y + 10 })
    await ann.waitForTimeout(300)
    const c1 = await frame(ann, circle.id)
    assert.ok(c1.w > c0.w, `grew: ${c0.w} -> ${c1.w}`)
    assert.ok(Math.abs(c1.w - c1.h) <= 2, `still round: ${c1.w} x ${c1.h}`)
    log('circle resized', c0, '->', c1)

    // ---- a rectangle has all eight handles
    await ann.click(`.obj[data-id="${shapes[0].id}"]`, { position: CORNER })
    await ann.waitForFunction(() => document.querySelectorAll('.mine .handle').length === 8)

    await ann.screenshot({ path: `${SHOTS}/slides-ann.png` })

    // ---- ann shares the presentation with ben, and he comes in and sees all of it
    await ann.click('.menus .title:text-is("File")')
    await ann.click('.menus [role=menuitem]:has-text("Share")')
    await ann.fill('.modal input >> nth=0', BEN[0])
    await ann.fill('.modal input >> nth=1', BEN[1])
    await ann.click('.modal button:has-text("Add person")')
    await ann.waitForSelector('.added')
    await ann.keyboard.press('Escape')
    const ben = await open(browser, BEN, false)
    await waitFor(ben, () => document.querySelectorAll('.obj').length === 4, null, 'four objects for ben')
    assert.ok((await objects(ben)).some((o) => o.text.includes('Hello slide')))
    assert.equal(await ben.locator('.obj svg path').count(), 3)
    log('ben sees', (await objects(ben)).length, 'objects')

    // ---- ann holds the rectangle: ben sees her mark, and cannot take it
    await waitFor(ben, () => document.querySelector('.other .tag')?.textContent === 'ann', null, "ann's selection")
    const held = shapes[0].id
    await ben.click(`.obj[data-id="${held}"]`, { position: CORNER })
    await waitFor(ben, () => document.querySelector('.toast.warning'), null, 'the refusal to select')
    log('ben was told:', await ben.locator('.toast').textContent())
    assert.equal(await ben.locator('.mine').count(), 0, 'ben holds nothing')

    // ---- ben takes the triangle and moves it; ann sees it move
    const triangle = shapes[2]
    const tb = await box(ben, triangle.id)
    const seen0 = await frame(ann, triangle.id)
    const left0 = parseFloat(await ann.locator(`.obj[data-id="${triangle.id}"]`).evaluate((e) => e.style.left))
    await drag(ben, centre(tb), { x: centre(tb).x + 150, y: centre(tb).y + 120 })
    await waitFor(ann, ([id, x]) => Math.abs(parseFloat(document.querySelector(`.obj[data-id="${id}"]`).style.left) - x) > 20, [triangle.id, left0], 'the triangle to move for ann')
    const seen1 = await frame(ann, triangle.id)
    assert.ok(seen1.x > seen0.x && seen1.y > seen0.y, `ann saw it move: ${seen0.x},${seen0.y} -> ${seen1.x},${seen1.y}`)
    log('ann saw ben move the triangle')
    assert.ok(await ann.locator('.other .tag:text-is("ben")').count(), "ann sees ben's mark")

    // ---- a viewer-free check of deleting: ann deletes the rectangle with the key; both see it go
    await ann.click(`.obj[data-id="${held}"]`, { position: CORNER })
    await ann.keyboard.press('Delete')
    await waitFor(ann, (id) => !document.querySelector(`.obj[data-id="${id}"]`), held, 'the rectangle to go')
    await waitFor(ben, (id) => !document.querySelector(`.obj[data-id="${id}"]`), held, 'the rectangle to go for ben')
    log('rectangle deleted, for both')

    // ---- ctrl+z brings it back, in the same place
    await ann.keyboard.press('Control+z')
    await waitFor(ann, (id) => document.querySelector(`.obj[data-id="${id}"]`), held, 'the rectangle to come back')
    await waitFor(ben, (id) => document.querySelector(`.obj[data-id="${id}"]`), held, 'the rectangle to come back for ben')
    const ids = (await objects(ann)).map((o) => o.id)
    assert.equal(ids.indexOf(held), 1, 'it is back at its place in the stack')
    log('undo restored it')

    // ---- the history lists what was done
    const entries = await ann.$$eval('.entry', (els) => els.map((e) => e.textContent.replace(/\s+/g, ' ').trim()))
    assert.ok(entries.some((e) => e.includes('Added a text box')), entries.join(' | '))
    assert.ok(entries.some((e) => e.includes('Moved an object')))
    assert.ok(entries.some((e) => e.includes('Resized an object')))
    assert.ok(entries.some((e) => e.includes('Removed an object')))

    // ---- a second slide
    await ann.click('button[aria-label="new slide"]')
    await waitFor(ann, () => document.querySelectorAll('.tabs [role=tab]').length === 2, null, 'the second slide')
    assert.equal((await objects(ann)).length, 0, 'the new slide is empty')
    await waitFor(ben, () => document.querySelectorAll('.tabs [role=tab]').length === 2, null, 'the second slide for ben')

    await ben.screenshot({ path: `${SHOTS}/slides-ben.png` })

    for (const [who, page] of [['ann', ann], ['ben', ben]]) assert.deepEqual(page.errors, [], `${who} saw errors`)
    log('ok')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error('FAILED:', e.message)
  process.exit(1)
})
