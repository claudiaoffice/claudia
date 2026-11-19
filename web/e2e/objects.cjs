// Objects in all three apps, in a real browser: one contract (D1221-D1230, notes/object-interaction-contract.md).
//
// For every kind of object an app can make, and in every app, the same things are done with it and the same things are
// expected: a press selects it (one frame, nothing below it takes the press), a drag moves it as a preview and changes
// the document once on release (Esc drops it), the handles scale it (proportions kept where the kind has them), the turn
// handle and Rotate by... turn it, a right press opens its own menu and no other, and the keyboard nudges, deselects and
// deletes it. Composes also has its tables, which are in the flow and have a menu, a name tab and a drop line of their
// own. A second person watches: what the first one does is what the second one has.
//
//   server 1: uv run python -m claudia_server --no-tls --model claudia_computes.model:WorkbookModel --port 8765 --web web/.output/public --dir /tmp/o1
//   server 2: ... --model claudia_composes:TextModel --port 8766 ...      server 3: ... --model claudia_creates:SlideModel --port 8767 ...
//   node e2e/objects.cjs                       (APP=computes|composes|creates for one; CHROME=/path/to/chrome; SHOTS=dir)
//
// D1232 (tests first, not built yet): Edit text for the words of a text box and a shape in composes, and Format ▸ Rotate
// (Rotate Right 90°, Rotate Left 90°, Rotate By…, with their keys) in composes and computes as in creates. Their steps
// run with D1232=1 and are not in CI until the features are built; then the gate goes and they are the contract.
//
// `tests/test_object_kinds_agree.py` fails when a kind of object (`claudia_core.OBJECT_KINDS`) has no row in KINDS below:
// a new kind of object comes with its row here, or says in its row why an app cannot have it.
const { chromium } = require('playwright')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const zlib = require('node:zlib')

const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const STAMP = Date.now() % 100000
const ANN = ['ann', 'Ann-has-a-Password-1']
const BEN = ['ben', 'Ben-has-a-Password-1']
const log = (...a) => console.log(...a)
const D1232 = process.env.D1232 === '1'

// -- a picture that is big enough to hold with a pointer: 200 x 100, a gradient so that it can be told from a hole
function png(w, h) {
  const table = Array.from({ length: 256 }, (_, n) => {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    return c >>> 0
  })
  const crc = (buf) => {
    let c = 0xffffffff
    for (const b of buf) c = table[(c ^ b) & 0xff] ^ (c >>> 8)
    return (c ^ 0xffffffff) >>> 0
  }
  const chunk = (type, data) => {
    const body = Buffer.concat([Buffer.from(type), data])
    const out = Buffer.alloc(body.length + 8)
    out.writeUInt32BE(data.length, 0)
    body.copy(out, 4)
    out.writeUInt32BE(crc(body), body.length + 4)
    return out
  }
  const head = Buffer.alloc(13)
  head.writeUInt32BE(w, 0)
  head.writeUInt32BE(h, 4)
  head[8] = 8 // bits
  head[9] = 2 // RGB
  const rows = Buffer.alloc((w * 3 + 1) * h)
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const at = y * (w * 3 + 1) + 1 + x * 3
      rows[at] = Math.round((255 * x) / w)
      rows[at + 1] = Math.round((255 * y) / h)
      rows[at + 2] = 160
    }
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', head), chunk('IDAT', zlib.deflateSync(rows)), chunk('IEND', Buffer.alloc(0))])
}
const PICTURE = png(200, 100)

// -- the three apps: where they are, how to see their objects, what is below an object that a press must not touch
const APPS = {
  computes: {
    url: process.env.URL_COMPUTES ?? 'http://127.0.0.1:8765/',
    ready: '[role=grid]',
    objects: '.viewport .object[data-object]',
    // the active cell: a press on an object must not move it
    below: (page) => page.$eval('.viewport .active', (e) => e.getAttribute('style')).catch(() => ''),
    // Edit text: only a container is written in (a picture and a chart have no words)
    editable: (kind) => kind === 'rendered',
    wrap: false,
    grid: false,
  },
  composes: {
    url: process.env.URL_COMPOSES ?? 'http://127.0.0.1:8766/',
    ready: '[data-testid=text]',
    objects: '[data-testid=containers] .object[data-object]',
    // the caret: a press on an object must not move it
    below: (page) =>
      page.evaluate(() => {
        const s = getSelection()
        const block = s?.anchorNode && (s.anchorNode.nodeType === 1 ? s.anchorNode : s.anchorNode.parentElement)?.closest('[data-block]')
        return JSON.stringify([block ? [...document.querySelectorAll('[data-block]')].indexOf(block) : -1, s?.anchorOffset ?? -1])
      }),
    // D1232: the words of a box or a shape are written as typed (`write_words`), as in creates
    editable: (kind) => kind === 'rendered' || (D1232 && kind !== 'image' && kind !== 'diagram'),
    wrap: true,
    grid: false,
  },
  creates: {
    url: process.env.URL_CREATES ?? 'http://127.0.0.1:8767/',
    ready: '[data-testid=slide]',
    objects: '[data-testid=slide] .obj',
    below: async () => '', // the slide has nothing under an object but the slide
    editable: () => true,
    wrap: false,
    grid: true,
  },
}

// -- the kinds of object, by app: how each is made. A kind an app cannot have says why instead of a function.
//    (`tests/test_object_kinds_agree.py` reads this block: one row for every kind in claudia_core.OBJECT_KINDS.)
const KINDS = {
  text: { computes: 'a cell grid has no text boxes', composes: (p) => menu(p, 'Edit', 'Text Box'), creates: (p) => menu(p, 'Edit', 'Text Box') },
  shape: {
    computes: 'a cell grid has no shapes',
    composes: (p) => menu(p, 'Edit', 'Rectangle'),
    creates: (p) => p.click('.bar button[aria-label="Rectangle"]'),
  },
  image: { computes: (p) => insertPicture(p), composes: (p) => insertPicture(p), creates: (p) => insertPicture(p) },
  diagram: { computes: (p) => insertChart(p), composes: 'a text has no charts', creates: 'a slide has no charts' },
  rendered: { computes: (p) => insertContainer(p), composes: (p) => insertContainer(p), creates: (p) => insertContainer(p) },
  table: { computes: 'a sheet is the table', composes: 'its own battery, below (tables are in the flow)', creates: 'a slide has no tables' },
}
// end of KINDS

// What each kind has in its menu: the contract (D1225), by what the kind and the app have.
function menuFor(app, kind) {
  const a = APPS[app]
  const items = ['Name & describe…']
  if (kind !== 'image' && kind !== 'diagram' && a.editable(kind)) items.push('Edit text')
  items.push('Style…')
  if (kind !== 'diagram') items.push('Rotate by…')
  if (a.wrap) items.push('Wrap text…')
  if (kind === 'image') items.push('Cut', 'Copy')
  if (a.grid) items.push(/^(Snap to grid|Release from grid)$/)
  items.push('Delete')
  return items
}

// -- plumbing
async function open(browser, app, [user, password], doc, create) {
  const a = APPS[app]
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 800 } })).newPage()
  page.errors = []
  page.on('pageerror', (e) => page.errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && page.errors.push('console: ' + m.text()))
  await page.goto(a.url)
  await page.fill('input[name=document]', doc)
  await page.fill('input[name=user]', user)
  await page.fill('input[name=password]', password)
  await page.click(create ? 'text=Create document' : 'button:text-is("Open")')
  if (create) {
    await page.waitForSelector('[data-testid=recovery-key]')
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
  }
  await page.waitForSelector(a.ready)
  await page.waitForFunction(() => document.querySelector('.health.open'))
  return page
}
async function menu(page, title, ...path) {
  await page.click(`.menus .title:text-is("${title}")`)
  for (const item of path) await page.click(`.menus .drop [role=menuitem]:has-text("${item}")`)
}
async function share(ann, [user, password]) {
  await menu(ann, 'File', 'Manage', 'Share')
  await ann.fill('.modal input >> nth=0', user)
  await ann.fill('.modal input >> nth=1', password)
  await ann.click('.modal button:has-text("Add person")')
  await ann.waitForSelector('.added')
  await ann.keyboard.press('Escape')
}
async function insertPicture(page) {
  await menu(page, 'Edit', 'Image…')
  await page.setInputFiles('.modal input[type=file]', { name: 'gradient.png', mimeType: 'image/png', buffer: PICTURE })
  await page.waitForSelector('.modal .preview img')
  await page.fill('.modal input[maxlength="300"]', 'a gradient, red to the right, green downwards')
  await page.click('.modal button[type=submit]')
}
async function insertChart(page) {
  // two columns of numbers, selected, as a floating object on the sheet
  await page.locator('.viewport').click({ position: { x: 52 + 40, y: 26 + 13 } })
  for (const text of ['1', '2', '3']) {
    await page.keyboard.type(text)
    await page.keyboard.press('Enter')
  }
  await page.locator('.viewport').click({ position: { x: 52 + 40, y: 26 + 13 } })
  await page.keyboard.press('Shift+ArrowDown')
  await page.keyboard.press('Shift+ArrowDown')
  await menu(page, 'Edit', 'Chart…')
  await page.check('.modal input[value=object]')
  await page.click('.modal button[type=submit]')
}
async function insertContainer(page) {
  await page.click('.menus .title:text-is("Insert")')
  await page.click('.menus .drop [role=menuitem]:has-text("Container")')
  const latex = page.locator('.menus .drop [role=menuitem]:has-text("LaTeX")')
  if (await latex.isDisabled()) {
    await page.keyboard.press('Escape')
    return 'skipped'
  }
  await latex.click()
  await page.keyboard.press('Escape') // a new container is open for writing: leave it as it is
  return undefined
}

const count = (page, app) => page.locator(APPS[app].objects).count()
const entries = (page) => page.locator('ol.log > li.entry').count()
const box = async (locator) => (await locator.boundingBox()) ?? assert.fail('the object is not on the screen')
const centre = (b) => ({ x: b.x + b.width / 2, y: b.y + b.height / 2 })
const moved = (a, b) => Math.hypot(a.x - b.x, a.y - b.y)
async function waitEntries(page, n, what) {
  try {
    await page.waitForFunction((n) => document.querySelectorAll('ol.log > li.entry').length === n, n, { timeout: 8000 })
  } catch {
    throw new Error(`${what}: the history has ${await entries(page)} entries, ${n} expected`)
  }
}
async function drag(page, from, to, { steps = 10, release = true } = {}) {
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(to.x, to.y, { steps })
  if (release) await page.mouse.up()
}
const frames = (page) => page.locator('[data-handle=se]').count()
const selectedCount = (page, app) => page.locator(`${APPS[app].objects}.selected`).count()
const turnAngle = async (page) => Number(await page.locator('[data-handle=turn]').getAttribute('aria-valuenow'))
const menuLabels = (page) =>
  page.$$eval('[role=menu][aria-label="Object menu"] > li > button > span:first-child', (els) => els.map((e) => e.textContent.replace(/[✓▸]/g, '').trim()))
// the right press leaves the one menu of the object, not the menu of a cell, a header or a paragraph beside it
const menusOpen = (page) => page.$$eval('[role=menu]', (els) => els.filter((e) => !e.closest('.menus') && !e.classList.contains('sub')).map((e) => e.getAttribute('aria-label')))

// -- the battery: what every object does, in every app
async function battery(app, kind, ann, ben) {
  const where = `${app} ${kind}`
  const a = APPS[app]
  const obj = ann.locator(a.objects)
  const turns = kind !== 'diagram'
  const hist0 = await entries(ann)
  assert.equal(await count(ann, app), 1, `${where}: one object was made`)
  if (ben) await ben.waitForFunction(([sel]) => document.querySelectorAll(sel).length === 1, [a.objects], { timeout: 8000 })

  // 1. a press selects, shows one frame, and is not heard by what lies below
  const belowBefore = await a.below(ann)
  await obj.click()
  await ann.waitForSelector(`${a.objects}.selected`)
  assert.equal(await selectedCount(ann, app), 1, `${where}: one object is selected`)
  assert.equal(await frames(ann), 1, `${where}: one frame, with its handles`)
  assert.equal(await ann.locator('[data-handle=turn]').count(), turns ? 1 : 0, `${where}: the turn handle is there for what turns`)
  assert.equal(await a.below(ann), belowBefore, `${where}: what lies below did not take the press`)
  assert.deepEqual(await menusOpen(ann), [], `${where}: a left press opens no menu`)
  log(`${where}: press selects`)

  // 2. a right press selects and opens the object's own menu, and only that one
  await obj.click({ button: 'right' })
  await ann.waitForSelector('[role=menu][aria-label="Object menu"]')
  const labels = await menuLabels(ann)
  const wanted = menuFor(app, kind)
  assert.equal(labels.length, wanted.length, `${where}: the menu has ${JSON.stringify(labels)}, expected ${wanted.map(String).join(' | ')}`)
  wanted.forEach((w, i) => assert.ok(w instanceof RegExp ? w.test(labels[i]) : w === labels[i], `${where}: menu entry ${i} is "${labels[i]}", expected ${w}`))
  assert.deepEqual(await menusOpen(ann), ['Object menu'], `${where}: no cell, paragraph or header menu beside the object's`)
  assert.equal(await a.below(ann), belowBefore, `${where}: the right press did not move what lies below`)
  await ann.keyboard.press('Escape')
  await ann.waitForSelector('[role=menu][aria-label="Object menu"]', { state: 'detached' })
  log(`${where}: right press menu`)

  // 2b. Edit text: the editor opens from the menu, Enter and a double press; what is typed is one entry; Esc takes it back
  if (a.editable(kind)) await editText(app, kind, ann, ben, obj)

  // 3. a drag moves a preview, the document changes once on release, and Esc takes a drag back
  await obj.click()
  const start = await box(obj)
  const h1 = await entries(ann)
  await drag(ann, centre(start), { x: centre(start).x + 90, y: centre(start).y + 50 }, { release: false })
  const during = await box(obj)
  assert.ok(moved(start, during) > 40, `${where}: the object follows the pointer while it is held`)
  assert.equal(await entries(ann), h1, `${where}: nothing is in the history while it is held`)
  await ann.mouse.up()
  await waitEntries(ann, h1 + 1, `${where}: one entry for the move`)
  const landed = await box(obj)
  assert.ok(moved(start, landed) > 20, `${where}: it stayed where it was dropped`)
  await drag(ann, centre(landed), { x: centre(landed).x + 70, y: centre(landed).y + 40 }, { release: false })
  await ann.keyboard.press('Escape')
  await ann.mouse.up()
  await ann.waitForTimeout(400)
  assert.ok(moved(landed, await box(obj)) < 2, `${where}: Esc takes the drag back`)
  assert.equal(await entries(ann), h1 + 1, `${where}: and leaves nothing in the history`)
  log(`${where}: drag`)

  // 4. the handles scale it, with its proportions where the kind has them
  await obj.click()
  const before = await box(obj)
  const h2 = await entries(ann)
  const se = centre(await box(ann.locator('[data-handle=se]')))
  await drag(ann, se, { x: se.x + 40, y: se.y + 20 })
  await waitEntries(ann, h2 + 1, `${where}: one entry for the size`)
  const after = await box(obj)
  assert.ok(after.width > before.width + 10 && after.height > before.height - 1, `${where}: it grew with the corner (${before.width}x${before.height} -> ${after.width}x${after.height})`)
  if (kind === 'image' || kind === 'shape') {
    const was = before.width / before.height
    const is = after.width / after.height
    assert.ok(Math.abs(is - was) / was < 0.03, `${where}: proportions kept (${was.toFixed(2)} -> ${is.toFixed(2)})`)
  }
  log(`${where}: handles`)

  // 5. the turn handle and Rotate by...
  if (turns) {
    const h3 = await entries(ann)
    const around = centre(await box(obj))
    const handle = centre(await box(ann.locator('[data-handle=turn]')))
    await drag(ann, handle, { x: around.x + 200, y: around.y }, { steps: 12 }) // straight up is 0, to the right is 90
    await waitEntries(ann, h3 + 1, `${where}: one entry for the turn`)
    const angle = await turnAngle(ann)
    assert.ok(angle >= 80 && angle <= 100, `${where}: turned to the right: ${angle}°`)
    await obj.click({ button: 'right' })
    await ann.getByRole('menuitem', { name: /^Rotate by…/ }).click()
    await ann.waitForSelector('form.rotate input[type=text]')
    await ann.fill('form.rotate input[type=text]', '30')
    await ann.keyboard.press('Enter')
    await ann.waitForFunction(() => document.querySelector('[data-handle=turn]')?.getAttribute('aria-valuenow') === '30', null, { timeout: 8000 })
    await waitEntries(ann, h3 + 2, `${where}: one entry for Rotate by…`)
    log(`${where}: turn`)
  } else {
    assert.equal(await ann.getByRole('menuitem', { name: /^Rotate by…/ }).count(), 0, `${where}: a chart is not turned`)
  }

  // 5b. Format ▸ Rotate, with its keys, in every app that turns objects (D1024, D1232)
  if (D1232) await rotateMenu(ann, where, turns, obj)

  // 6. the keyboard: arrows nudge, Esc deselects, Delete deletes (and Undo brings it back)
  await obj.click()
  const resting = await box(obj)
  await ann.keyboard.press('ArrowRight')
  await ann.waitForTimeout(400)
  assert.ok(moved(resting, await box(obj)) > 1, `${where}: an arrow key nudges it`)
  await ann.keyboard.press('Escape')
  await ann.waitForFunction(([sel]) => document.querySelectorAll(sel + '.selected').length === 0, [a.objects])
  assert.equal(await frames(ann), 0, `${where}: Esc deselects, the frame is gone`)
  await obj.click()
  const h4 = await entries(ann)
  await ann.keyboard.press('Delete')
  await ann.waitForFunction(([sel]) => document.querySelectorAll(sel).length === 0, [a.objects], { timeout: 8000 })
  assert.ok((await entries(ann)) > h4, `${where}: Delete is in the history`)
  if (ben) await ben.waitForFunction(([sel]) => document.querySelectorAll(sel).length === 0, [a.objects], { timeout: 8000 })
  await ann.keyboard.press('Control+z')
  await ann.waitForFunction(([sel]) => document.querySelectorAll(sel).length === 1, [a.objects], { timeout: 8000 })
  if (ben) await ben.waitForFunction(([sel]) => document.querySelectorAll(sel).length === 1, [a.objects], { timeout: 8000 })
  await obj.click()
  await ann.keyboard.press('Delete') // and away, for the next kind
  await ann.waitForFunction(([sel]) => document.querySelectorAll(sel).length === 0, [a.objects], { timeout: 8000 })
  assert.ok((await entries(ann)) > hist0, `${where}: all of it is in the history`)
  log(`${where}: keyboard, delete, undo, and ben saw it all`)
}

// -- Edit text: one editor, whatever the app (creates' paragraph editor, composes' box, a container's source)
async function editText(app, kind, ann, ben, obj) {
  const where = `${app} ${kind}`
  const rendered = kind === 'rendered'
  const editor = obj.locator(rendered ? '[data-testid=rendered-editor] textarea' : '[role=textbox]')
  const accept = rendered ? 'Control+Enter' : 'Enter'
  const words = rendered ? 'x^2 + y^2' : 'words by ann'
  const h = await entries(ann)
  // from the object's menu
  await obj.click({ button: 'right' })
  await ann.getByRole('menuitem', { name: /^Edit text/ }).click()
  await editor.waitFor()
  assert.equal(await editor.evaluate((e) => e === document.activeElement), true, `${where}: the editor has the keyboard`)
  await ann.keyboard.type(words)
  await ann.keyboard.press(accept)
  await editor.waitFor({ state: 'detached' })
  await waitEntries(ann, h + 1, `${where}: one entry for the words`)
  if (!rendered) {
    assert.ok((await obj.innerText()).includes(words), `${where}: the words are on the object`)
    if (ben) await ben.waitForFunction(([sel, text]) => document.querySelector(sel)?.textContent.includes(text), [APPS[app].objects, words])
  }
  // Enter on the selected object, and Esc leaves it as it was
  await obj.click()
  await ann.keyboard.press('Enter')
  await editor.waitFor()
  await ann.keyboard.type(' not kept')
  await ann.keyboard.press('Escape')
  await editor.waitFor({ state: 'detached' })
  await ann.waitForTimeout(300)
  assert.equal(await entries(ann), h + 1, `${where}: Esc leaves nothing in the history`)
  if (!rendered) assert.ok(!(await obj.innerText()).includes('not kept'), `${where}: and the words as they were`)
  // a double press opens it, too
  await obj.dblclick()
  await editor.waitFor()
  await ann.keyboard.press('Escape')
  await editor.waitFor({ state: 'detached' })
  log(`${where}: edit text`)
}

// -- Format ▸ Rotate: the same three entries and keys in every app; not for a chart, not for nothing selected
async function rotateEntries(page) {
  await page.click('.menus .title:text-is("Format")')
  await page.click('.menus .drop [role=menuitem]:has-text("Rotate")')
}
async function rotateOff(page, where) {
  await rotateEntries(page)
  for (const name of ['Rotate Right 90°', 'Rotate Left 90°', 'Rotate By…'])
    assert.equal(await page.locator(`.menus .drop [role=menuitem]:has-text("${name}")`).isDisabled(), true, `${where}: ${name} is off`)
  await page.keyboard.press('Escape')
}
async function rotateMenu(ann, where, turns, obj) {
  await obj.click()
  if (!turns) {
    await rotateOff(ann, `${where}: a chart`)
    return
  }
  const angle = await turnAngle(ann)
  const h = await entries(ann)
  const turnedTo = (degrees) => ann.waitForFunction((d) => Number(document.querySelector('[data-handle=turn]')?.getAttribute('aria-valuenow')) === d, degrees, { timeout: 8000 })
  await menu(ann, 'Format', 'Rotate', 'Rotate Right 90°')
  await turnedTo((angle + 90) % 360)
  await menu(ann, 'Format', 'Rotate', 'Rotate Left 90°')
  await turnedTo(angle)
  await ann.keyboard.press('Control+Alt+Period')
  await turnedTo((angle + 90) % 360)
  await ann.keyboard.press('Control+Alt+Comma')
  await turnedTo(angle)
  await waitEntries(ann, h + 4, `${where}: one entry for each quarter turn`)
  await menu(ann, 'Format', 'Rotate', 'Rotate By…')
  await ann.waitForSelector('form.rotate input[type=text]')
  await ann.fill('form.rotate input[type=text]', '45')
  await ann.keyboard.press('Enter')
  await turnedTo(45)
  await waitEntries(ann, h + 5, `${where}: one entry for Rotate By…`)
  await ann.keyboard.press('Control+Shift+Alt+Z')
  await ann.waitForSelector('form.rotate input[type=text]')
  await ann.keyboard.press('Escape')
  await ann.waitForSelector('form.rotate', { state: 'detached' })
  assert.equal(await entries(ann), h + 5, `${where}: Rotate By… left with Esc changes nothing`)
  log(`${where}: Format ▸ Rotate and its keys`)
}

// -- composes' tables: in the flow, a name tab to hold, a drop line between paragraphs, a menu of their own
async function tables(ann, ben) {
  const where = 'composes table'
  const table = ann.locator('[data-testid=table]')
  await ann.click('[data-testid=text]')
  for (const words of ['The first paragraph.', 'The second paragraph.', 'The third paragraph.']) {
    await ann.keyboard.type(words)
    await ann.keyboard.press('Enter')
  }
  await ann.waitForFunction(() => document.querySelectorAll('[data-testid=text] [data-block]').length >= 3)
  await ann.locator('[data-testid=text] [data-block]').nth(0).click()
  await menu(ann, 'Insert', 'Table…')
  await ann.fill('[data-testid=table-cols]', '3')
  await ann.fill('[data-testid=table-rows]', '2')
  await ann.click('[data-testid=table-insert]')
  await table.waitFor()
  if (ben) await ben.locator('[data-testid=table]').waitFor()
  assert.equal(await table.count(), 1, `${where}: a table was made`)
  assert.equal(await ann.locator('[data-testid=containers] [data-object][data-testid=table]').count(), 0, `${where}: the layer of objects does not draw it a second time`)

  // select with a press on the tab; Options... is its chip; no other kind of frame is drawn around it
  const tab = ann.locator('[data-testid=table-tab]')
  await tab.click()
  await ann.waitForSelector('[data-testid=table].selected')
  assert.equal(await ann.locator('[data-testid=table-options]').isVisible(), true, `${where}: the Options… chip is there and not covered`)
  await ann.click('[data-testid=table-options]')
  await ann.waitForSelector('.modal, dialog[open]')
  await ann.keyboard.press('Escape')
  log(`${where}: tab selects, Options…`)

  // right press on the tab: the table's menu, and no other
  await tab.click({ button: 'right' })
  await ann.waitForSelector('[role=menu][aria-label="Object menu"]')
  assert.deepEqual(await menuLabels(ann), ['Name & describe…', 'Table options…', 'Merge cells', 'Split cell', 'Sort', 'Delete table'], `${where}: the table's menu`)
  assert.deepEqual(await menusOpen(ann), ['Object menu'], `${where}: not the menu of a paragraph beside it`)
  await ann.keyboard.press('Escape')
  await ann.waitForSelector('[role=menu][aria-label="Object menu"]', { state: 'detached' })

  // drag the tab below the last paragraph: a drop line while held, one entry on release, Esc leaves the table
  const first = await box(table)
  const h1 = await entries(ann)
  const last = await box(ann.locator('[data-testid=text] [data-block]').last())
  await drag(ann, centre(await box(tab)), { x: last.x + 40, y: last.y + last.height - 2 }, { release: false })
  await ann.waitForSelector('[data-testid=table-drop-line]')
  await ann.mouse.up()
  await waitEntries(ann, h1 + 1, `${where}: one entry for the move`)
  assert.ok((await box(table)).y > first.y + 10, `${where}: it is lower, between other paragraphs`)
  assert.equal(await ann.locator('[data-testid=table-drop-line]').count(), 0, `${where}: the drop line is gone`)
  await tab.click()
  await ann.keyboard.press('Escape')
  await ann.waitForFunction(() => document.querySelectorAll('[data-testid=table].selected').length === 0)
  log(`${where}: drop line, one entry, Esc leaves it`)

  // Delete takes a selected table away, whatever it was selected with; Undo brings it back
  await tab.click()
  await ann.keyboard.press('Delete')
  await ann.waitForFunction(() => document.querySelectorAll('[data-testid=table]').length === 0, null, { timeout: 8000 })
  if (ben) await ben.waitForFunction(() => document.querySelectorAll('[data-testid=table]').length === 0, null, { timeout: 8000 })
  await ann.keyboard.press('Control+z')
  await ann.waitForSelector('[data-testid=table]')
  log(`${where}: Delete, Undo, and ben saw it`)
}

// -- one app: make the document, share it, run the battery for every kind the app can make
async function run(browser, app) {
  const doc = `objects-${app}-${STAMP}`
  const ann = await open(browser, app, ANN, doc, true)
  await share(ann, BEN)
  const ben = await open(browser, app, BEN, doc, false)
  try {
    if (app === 'composes') {
      await ann.click('[data-testid=text]')
      for (let i = 0; i < 3; i++) {
        await ann.keyboard.type('Some words so that there is something below an object. '.repeat(3))
        await ann.keyboard.press('Enter')
      }
      await ann.waitForTimeout(500)
      await ann.keyboard.press('Control+Home')
    }
    if (D1232) await rotateOff(ann, `${app}: nothing is selected`)
    for (const [kind, row] of Object.entries(KINDS)) {
      const make = row[app]
      if (typeof make === 'string') {
        log(`${app} ${kind}: none (${make})`)
        continue
      }
      if (kind === 'table') continue
      if ((await make(ann)) === 'skipped') {
        log(`${app} ${kind}: skipped, the server has no tool for it`)
        continue
      }
      await ann.waitForFunction(([sel]) => document.querySelectorAll(sel).length === 1, [APPS[app].objects], { timeout: 15000 })
      await battery(app, kind, ann, ben)
    }
    if (app === 'composes') await tables(ann, ben)
    assert.deepEqual(ann.errors, [], `${app}: no errors on the page (ann)`)
    assert.deepEqual(ben.errors, [], `${app}: no errors on the page (ben)`)
    log(`${app}: ok`)
  } catch (e) {
    fs.mkdirSync(SHOTS, { recursive: true })
    await ann.screenshot({ path: `${SHOTS}/objects-${app}-fail.png` }).catch(() => undefined)
    throw e
  }
}

;(async () => {
  const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME, args: ['--no-sandbox'] } : {})
  try {
    for (const app of process.env.APP ? [process.env.APP] : Object.keys(APPS)) await run(browser, app)
    log('objects: ok')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error(e)
  process.exitCode = 1
})
