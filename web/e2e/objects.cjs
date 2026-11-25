// Objects in all three apps, in a real browser: one contract (D1221-D1230, notes/object-interaction-contract.md).
//
// For every kind of object an app can make, and in every app, the same things are done with it and the same things are
// expected: a press selects it (one frame, nothing below it takes the press), a drag moves it as a preview and changes
// the document once on release (Esc drops it), the handles scale it (proportions kept where the kind has them), the turn
// handle and Rotate by... turn it, a right press opens its own menu and no other, and the keyboard nudges, deselects and
// deletes it. Composes also has its tables, which are in the flow and have a menu, a name tab and a drop line of their
// own. A second person watches: what the first one does is what the second one has, and what the first one has selected
// the second sees in her colour, with her name, and cannot change (D1223).
//
//   server 1: uv run python -m claudia_server --no-tls --model claudia_computes.model:WorkbookModel --port 8765 --web web/.output/public --dir /tmp/o1
//   server 2: ... --model claudia_composes:TextModel --port 8766 ...      server 3: ... --model claudia_creates:SlideModel --port 8767 ...
//   node e2e/objects.cjs                       (APP=computes|composes|creates for one; CLAUDIA_CHROMIUM=/path/to/chrome; SHOTS=dir)
//
// D1232: Edit text writes the words of a text box and a shape in composes as it does in creates, and Format ▸ Rotate
// (Rotate Right 90°, Rotate Left 90°, Rotate By…, with their keys) is in composes and computes as in creates; neither a
// chart nor a table turns (D1021, D1224), in the menu as on the server.
//
// `tests/test_object_kinds_agree.py` fails when a kind of object (`claudia_core.OBJECT_KINDS`) has no row in KINDS below:
// a new kind of object comes with its row here, or says in its row why an app cannot have it.
const { launch } = require('./browser.cjs')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const zlib = require('node:zlib')

const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const STAMP = Date.now() % 100000
const ANN = ['ann', 'Ann-has-a-Password-1']
const BEN = ['ben', 'Ben-has-a-Password-1']
const log = (...a) => console.log(...a)

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
    editable: (kind) => kind === 'container',
    wrap: false,
    grid: false,
  },
  composes: {
    url: process.env.URL_COMPOSES ?? 'http://127.0.0.1:8766/',
    ready: '[data-testid=text]',
    objects: '[data-testid=object-layer] .object[data-object]',
    // the caret: a press on an object must not move it
    below: (page) =>
      page.evaluate(() => {
        const s = getSelection()
        const paragraph = s?.anchorNode && (s.anchorNode.nodeType === 1 ? s.anchorNode : s.anchorNode.parentElement)?.closest('[data-paragraph]')
        return JSON.stringify([paragraph ? [...document.querySelectorAll('[data-paragraph]')].indexOf(paragraph) : -1, s?.anchorOffset ?? -1])
      }),
    // D1232: the words of a box or a shape are written as typed (`write_words`), as in creates
    editable: (kind) => kind !== 'image' && kind !== 'chart',
    wrap: true,
    grid: false,
  },
  creates: {
    url: process.env.URL_CREATES ?? 'http://127.0.0.1:8767/',
    ready: '[data-testid=slide]',
    objects: '[data-testid=slide] .obj',
    below: async () => '', // the slide has nothing under an object but the slide
    editable: (kind) => kind !== 'image' && kind !== 'chart', // a picture and a chart have no words (D1225)
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
  chart: { computes: (p) => insertChart(p), composes: 'a text has no charts', creates: 'a slide has no charts' },
  container: { computes: (p) => insertContainer(p), composes: (p) => insertContainer(p), creates: (p) => insertContainer(p) },
  table: { computes: 'a sheet is the table', composes: 'its own battery, below (tables are in the flow)', creates: 'a slide has no tables' },
}
// end of KINDS

// What each kind has in its menu: the contract (D1225), by what the kind and the app have.
function menuFor(app, kind) {
  const a = APPS[app]
  const items = ['Name & describe…']
  if (kind !== 'image' && kind !== 'chart' && a.editable(kind)) items.push('Edit text')
  items.push('Style…')
  if (kind !== 'chart') items.push('Rotate by…')
  if (a.wrap) items.push('Wrap text…')
  if (kind === 'chart' && app === 'computes') items.push('Move to Slide') // a chart on a sheet (E6.31, D1475)
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
  await page.check('.modal input[value=sheet]')
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
/** The object leaves the screen at once; its entry in the history comes with the server's answer, a moment later. */
async function moreEntriesThan(page, n, what) {
  try {
    await page.waitForFunction((n) => document.querySelectorAll('ol.log > li.entry').length > n, n, { timeout: 8000 })
  } catch {
    throw new Error(`${what}: the history has ${await entries(page)} entries, more than ${n} expected`)
  }
}
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

// -- what a second window sees while ann has an object selected (D1223, D1231, PROC-29): ann's colour round it and her
// name; its own change of the object is refused and nothing changes (`tryIt` is that change, made in ben's window,
// which returns once ben was told no); ann lets go (`letGo`, in her window), and her name goes
const ANN_MARK = '[data-testid=other-on-object][data-user=ann]'
/** Ben is told that ann is working there: the server's answer to what he tried. */
async function toldNo(ben) {
  await ben.waitForFunction(() => document.querySelector('.toast')?.textContent.includes('ann'), null, { timeout: 8000 })
}
/** Ben's notice is cleared, so that the next one is the answer to what he tries next. */
async function noNotice(ben) {
  await ben.evaluate(() => document.querySelector('.toast')?.click())
  await ben.waitForFunction(() => !document.querySelector('.toast'), null, { timeout: 8000 })
}
async function watched(where, ann, ben, { tryIt, unchanged, letGo }) {
  await ben.waitForSelector(ANN_MARK, { timeout: 8000 })
  const hers = await ann.$eval('ul.people li', (e) => getComputedStyle(e).backgroundColor)
  const seen = await ben.$eval(ANN_MARK, (e) => [getComputedStyle(e).borderTopColor, e.textContent.trim()])
  assert.deepEqual(seen, [hers, 'ann'], `${where}: ben sees ann's colour round what she selected, and her name`)
  fs.mkdirSync(SHOTS, { recursive: true })
  await ben.screenshot({ path: `${SHOTS}/objects-${where.replace(' ', '-')}-watched.png` })
  const h = await entries(ann)
  await noNotice(ben)
  await tryIt()
  await unchanged()
  assert.equal(await entries(ann), h, `${where}: what ben tried while ann has it is not in the history`)
  await letGo()
  await ben.waitForSelector(ANN_MARK, { state: 'detached', timeout: 8000 })
  log(`${where}: ben sees ann's selection, cannot change it, and it goes`)
}
const menuLabels = (page, name = 'Object menu') =>
  page.$$eval(`[role=menu][aria-label="${name}"] > li > button > span:first-child`, (els) => els.map((e) => e.textContent.replace(/[✓▸]/g, '').trim()))
// the right press leaves the one menu of the object, not the menu of a cell, a header or a paragraph beside it
const menusOpen = (page) => page.$$eval('[role=menu]', (els) => els.filter((e) => !e.closest('.menus') && !e.classList.contains('sub')).map((e) => e.getAttribute('aria-label')))

// -- the battery: what every object does, in every app
async function battery(app, kind, ann, ben) {
  const where = `${app} ${kind}`
  const a = APPS[app]
  const obj = ann.locator(a.objects)
  const turns = kind !== 'chart' && kind !== 'table'
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

  // 1b. ben sees it, and his drag of it is refused (D1223)
  if (ben) {
    const was = await box(obj)
    await watched(where, ann, ben, {
      tryIt: async () => {
        const before = await box(ben.locator(a.objects))
        await drag(ben, centre(before), { x: centre(before).x + 80, y: centre(before).y + 40 })
        await toldNo(ben)
        // and his own window shows it where it is
        await ben.waitForFunction(
          ([sel, x, y]) => {
            const r = document.querySelector(sel).getBoundingClientRect()
            return Math.hypot(r.x - x, r.y - y) < 2
          },
          [a.objects, before.x, before.y],
          { timeout: 8000 },
        )
      },
      unchanged: async () => assert.ok(moved(was, await box(obj)) < 2, `${where}: ben's drag did not move what ann has selected`),
      letGo: async () => {
        await ann.keyboard.press('Escape')
        await ann.waitForFunction(([sel]) => document.querySelectorAll(sel + '.selected').length === 0, [a.objects])
      },
    })
  }

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
  // what keeps its proportions shows corner handles only (the contract); a rectangle is free and shows the edges as well
  const keepsAspect = kind === 'image' || (await ann.locator('[data-handle=n]').count()) === 0
  const se = centre(await box(ann.locator('[data-handle=se]')))
  await drag(ann, se, { x: se.x + 40, y: se.y + 20 })
  await waitEntries(ann, h2 + 1, `${where}: one entry for the size`)
  const after = await box(obj)
  assert.ok(after.width > before.width + 10 && after.height > before.height - 1, `${where}: it grew with the corner (${before.width}x${before.height} -> ${after.width}x${after.height})`)
  if (keepsAspect) {
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
    await ann.keyboard.press('Backspace') // the keys typed in the dialog are the dialog's: the object stays (UX-56)
    assert.equal(await count(ann, app), 1, `${where}: Backspace in the angle field did not delete the object`)
    await ann.fill('form.rotate input[type=text]', '30')
    await ann.keyboard.press('Enter')
    await ann.waitForFunction(() => document.querySelector('[data-handle=turn]')?.getAttribute('aria-valuenow') === '30', null, { timeout: 8000 })
    await waitEntries(ann, h3 + 2, `${where}: one entry for Rotate by…`)
    log(`${where}: turn`)
  } else {
    assert.equal(await ann.getByRole('menuitem', { name: /^Rotate by…/ }).count(), 0, `${where}: a chart is not turned`)
  }

  // 5b. Format ▸ Rotate, with its keys, in every app that turns objects (D1024, D1232)
  await rotateMenu(ann, where, turns, obj)

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
  await moreEntriesThan(ann, h4, `${where}: Delete is in the history`)
  if (ben) await ben.waitForFunction(([sel]) => document.querySelectorAll(sel).length === 0, [a.objects], { timeout: 8000 })
  await ann.keyboard.press('Control+z')
  await ann.waitForFunction(([sel]) => document.querySelectorAll(sel).length === 1, [a.objects], { timeout: 8000 })
  if (ben) await ben.waitForFunction(([sel]) => document.querySelectorAll(sel).length === 1, [a.objects], { timeout: 8000 })
  await obj.click()
  await ann.keyboard.press('Delete') // and away, for the next kind
  await ann.waitForFunction(([sel]) => document.querySelectorAll(sel).length === 0, [a.objects], { timeout: 8000 })
  await moreEntriesThan(ann, hist0, `${where}: all of it is in the history`)
  log(`${where}: keyboard, delete, undo, and ben saw it all`)
}

// -- Edit text: one editor, whatever the app (creates' paragraph editor, composes' box, a container's source)
async function editText(app, kind, ann, ben, obj) {
  const where = `${app} ${kind}`
  const isContainer = kind === 'container'
  const editor = obj.locator(isContainer ? '[data-testid=container-editor] textarea' : '[role=textbox]')
  const accept = isContainer ? 'Control+Enter' : 'Enter'
  const words = isContainer ? 'x^2 + y^2' : 'words by ann'
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
  if (!isContainer) {
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
  if (!isContainer) assert.ok(!(await obj.innerText()).includes('not kept'), `${where}: and the words as they were`)
  // a double press opens it, too
  await obj.dblclick()
  await editor.waitFor()
  await ann.keyboard.press('Escape')
  await editor.waitFor({ state: 'detached' })
  log(`${where}: edit text`)
}

// -- Format ▸ Rotate: the same three entries and keys in every app; not for a chart, not for nothing selected
async function rotateOff(page, where) {
  // With nothing to turn the whole Rotate submenu is off (it used to open with its three entries off): either says it.
  await page.click('.menus .title:text-is("Format")')
  const submenu = page.locator('.menus .drop [role=menuitem]:has-text("Rotate")').first()
  if (await submenu.isDisabled()) {
    await page.keyboard.press('Escape')
    return
  }
  await submenu.click()
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
  // the quarter turns' keys (Ctrl+Alt+. and ,) left with their entries (the menu workbook)
  await waitEntries(ann, h + 2, `${where}: one entry for each quarter turn`)
  await menu(ann, 'Format', 'Rotate', 'Rotate By…')
  await ann.waitForSelector('form.rotate input[type=text]')
  await ann.fill('form.rotate input[type=text]', '45')
  await ann.keyboard.press('Enter')
  await turnedTo(45)
  await waitEntries(ann, h + 3, `${where}: one entry for Rotate By…`)
  await ann.keyboard.press('Control+Shift+Alt+Z')
  await ann.waitForSelector('form.rotate input[type=text]')
  await ann.keyboard.press('Escape')
  await ann.waitForSelector('form.rotate', { state: 'detached' })
  assert.equal(await entries(ann), h + 3, `${where}: Rotate By… left with Esc changes nothing`)
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
  await ann.waitForFunction(() => document.querySelectorAll('[data-testid=text] [data-paragraph]').length >= 3)
  await ann.locator('[data-testid=text] [data-paragraph]').nth(0).click()
  await menu(ann, 'Insert', 'Table…')
  await ann.fill('[data-testid=table-cols]', '3')
  await ann.fill('[data-testid=table-rows]', '2')
  await ann.click('[data-testid=table-insert]')
  await table.waitFor()
  if (ben) await ben.locator('[data-testid=table]').waitFor()
  assert.equal(await table.count(), 1, `${where}: a table was made`)
  assert.equal(await ann.locator('[data-testid=object-layer] [data-object][data-testid=table]').count(), 0, `${where}: the layer of objects does not draw it a second time`)

  // select with a press on the tab; Options... is its chip; no other kind of frame is drawn around it
  const tab = ann.locator('[data-testid=table-tab]')
  await tab.click()
  await ann.waitForSelector('[data-testid=table].selected')
  assert.equal(await ann.locator('[data-testid=table-options]').isVisible(), true, `${where}: the Options… chip is there and not covered`)
  await ann.click('[data-testid=table-options]')
  await ann.waitForSelector('.modal, dialog[open]')
  await ann.keyboard.press('Escape')
  log(`${where}: tab selects, Options…`)

  // ben sees it, and his Delete of it is refused (D1223)
  if (ben)
    await watched(where, ann, ben, {
      tryIt: async () => {
        await ben.locator('[data-testid=table-tab]').click()
        await toldNo(ben)
        await noNotice(ben)
        await ben.keyboard.press('Delete')
        await toldNo(ben)
      },
      unchanged: async () => assert.equal(await table.count(), 1, `${where}: ben's Delete did not take away what ann has selected`),
      letGo: async () => {
        await tab.click()
        await ann.keyboard.press('Escape')
        await ann.waitForFunction(() => document.querySelectorAll('[data-testid=table].selected').length === 0)
      },
    })

  // right press on the tab: the table's menu, and no other
  await tab.click({ button: 'right' })
  await ann.waitForSelector('[role=menu][aria-label="Table menu"]')
  assert.deepEqual(await menuLabels(ann, 'Table menu'), ['Name & describe…', 'Table options…', 'Merge cells', 'Split cell', 'Sort', 'Delete table'], `${where}: the table's menu`)
  assert.deepEqual(await menusOpen(ann), ['Table menu'], `${where}: not the menu of a paragraph beside it`)
  await ann.keyboard.press('Escape')
  await ann.waitForSelector('[role=menu][aria-label="Table menu"]', { state: 'detached' })
  // a table does not turn: no Rotate by… in its menu above, and Format ▸ Rotate is off with it selected (D1224)
  await rotateOff(ann, `${where}: a table`)

  // drag the tab below the last paragraph: a drop line while held, one entry on release, Esc leaves the table
  const first = await box(table)
  const h1 = await entries(ann)
  const last = await box(ann.locator('[data-testid=text] [data-paragraph]').last())
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
    await rotateOff(ann, `${app}: nothing is selected`)
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
      // the object is drawn as soon as the server tells of it; the dialog that made it closes, and gives the focus
      // back, once it is selected and locked as well (D1223): only then is what lies below where it stays
      await ann.waitForFunction(() => !document.querySelector('.modal'), null, { timeout: 8000 })
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
  const browser = await launch()
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
