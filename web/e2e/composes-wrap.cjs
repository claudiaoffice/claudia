// Text goes round a text box in the flowing editor (CODE-64, D1068), and the one key goes round the wrap modes (D1064), in a real browser (server: --model claudia_composes:TextModel).
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8766/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `essay-${Date.now() % 100000}`
const ANN = ['ann', 'Ann has a password 1']

async function open(browser, [user, password], create) {
  const context = await browser.newContext({ viewport: { width: 1360, height: 800 } })
  const page = await context.newPage()
  await page.addInitScript(INIT)
  page.errors = []
  if (process.env.DEBUG) page.on('websocket', (ws) => ws.on('framesent', (f) => { const m = JSON.parse(f.payload); if (['replace_text','hold','look'].includes(m.method)) console.log(`[${user}] ->`, m.method, JSON.stringify(m.params)) }))
  page.on('pageerror', (e) => page.errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && page.errors.push('console: ' + m.text()))
  await page.goto(URL)
  await page.fill('input[name=document]', DOC)
  await page.fill('input[name=user]', user)
  await page.fill('input[name=password]', password)
  await page.click(create ? 'text=Create document' : 'button:text-is("Open")')
  if (create) {
    // a new document first shows its recovery key; the person must confirm having stored it
    await page.waitForSelector('[data-testid=recovery-key]')
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
  }
  await page.waitForSelector('[data-testid=text]')
  await page.waitForFunction(() => document.querySelector('.health.open'))
  return page
}

// The text of the paragraphs: what the model holds, without what only the screen shows (carets, previews of suggestions)
const textOf = () =>
  [...document.querySelectorAll('[data-testid=text] [data-paragraph]')].map((e) => {
    const copy = e.cloneNode(true)
    copy.querySelectorAll('[data-skip]').forEach((x) => x.remove())
    return copy.textContent
  })
const paragraphs = (page) => page.evaluate(textOf)
const INIT = `window.__text = ${textOf.toString()}`

const log2 = (...a) => console.log(...a)
const WORDS = Array.from({ length: 90 }, (_, i) => `word${(i * 7) % 97}`).join(' ')

// The words of the text that lie over an object's box (kept `gap` away): none, when the lines go round it.
const overlapping = (page, objectId, gap) =>
  page.evaluate(
    ([id, gap]) => {
      const o = document.querySelector(`[data-object="${id}"]`).getBoundingClientRect()
      let hits = 0
      for (const seg of document.querySelectorAll('[data-testid=text] [data-seg]')) {
        const t = seg.firstChild
        const re = /\S+/g
        let m
        while ((m = re.exec(t.data))) {
          const r = document.createRange()
          r.setStart(t, m.index)
          r.setEnd(t, m.index + m[0].length)
          for (const c of r.getClientRects()) {
            const x = c.left < o.right + gap - 1 && c.right > o.left - gap + 1
            const y = c.top < o.bottom + gap - 1 && c.bottom > o.top - gap + 1
            if (x && y) hits++
          }
        }
      }
      return hits
    },
    [objectId, gap],
  )
async function menu(page, title, ...path) {
  await page.click(`.menus .title:text-is("${title}")`)
  for (const item of path) await page.click(`.menus .drop [role=menuitem]:has-text("${item}")`)
}
const objectIds = (page) => page.$$eval('[data-object]', (els) => els.map((e) => e.dataset.object))


;(async () => {
  const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME, args: ['--no-sandbox'] } : {})
  try {
    const ann = await open(browser, ANN, true)
    await ann.click('[data-testid=text]')
    await ann.keyboard.type(WORDS)
    await ann.keyboard.press('Enter')
    await ann.keyboard.type(WORDS)
    await ann.keyboard.press('Enter')
    await ann.keyboard.type(WORDS)
    // everything typed has come back from the server (the status line counts the words), then the caret goes to the
    // start of the first paragraph: a caret put there while the last words are still on their way is moved again
    await ann.waitForFunction(() => /270 words/.test(document.body.innerText))
    await ann.waitForTimeout(500)
    await ann.keyboard.press('Control+Home')

    // ---- a text box goes into the text above and below the words, as D1061 has it
    await menu(ann, 'Edit', 'Text Box')
    await ann.waitForSelector('[data-testid=object-layer] [data-object]')
    const [box] = await objectIds(ann)
    assert.ok(box, 'a text box was made')
    await ann.waitForSelector('[data-testid=text] .wrap-float')
    await ann.waitForTimeout(600)
    await ann.screenshot({ path: `${SHOTS}/wrap-above-below.png` })
    assert.equal(await overlapping(ann, box, 8), 0, 'above and below: no word lies over the box')
    assert.equal(await ann.locator('[data-testid=text] .wrap-float').count(), 1)
    log2('above and below: ok')

    // ---- Format ▸ Wrap Text: the one key goes round the modes (over, around, above and below, behind, over)
    await ann.locator(`[data-object="${box}"]`).focus()
    await ann.keyboard.press('Control+Alt+r') // above and below -> behind
    await ann.waitForSelector('[data-testid=object-layer-behind] [data-object]')
    assert.equal(await ann.locator('[data-testid=text] .wrap-float').count(), 0, 'behind: nothing takes room')
    await ann.waitForFunction(
      (id) => {
        const o = document.querySelector(`[data-object="${id}"]`).getBoundingClientRect()
        const first = document.querySelector('[data-testid=text] [data-paragraph]').getBoundingClientRect()
        return o.top < first.top + 40 // the words are back under it, where the room was
      },
      box,
    )
    assert.ok((await overlapping(ann, box, 0)) > 0, 'behind: the words run over it')
    // Ctrl held: the object behind the words can be taken hold of, and the pointer says so
    await ann.keyboard.down('Control')
    await ann.waitForSelector('[data-testid=object-layer-behind].grab')
    const cursor = await ann.locator(`[data-object="${box}"]`).evaluate((e) => getComputedStyle(e).cursor)
    assert.equal(cursor, 'grab')
    await ann.keyboard.up('Control')
    assert.equal(await ann.locator('[data-testid=object-layer-behind].grab').count(), 0, 'without Ctrl the words have the press')
    log2('behind and Ctrl: ok')

    await ann.locator(`[data-object="${box}"]`).focus()
    await ann.keyboard.press('Control+Alt+r') // behind -> over
    await ann.waitForSelector('[data-testid=object-layer] [data-object]')
    assert.equal(await ann.locator('[data-testid=text] .wrap-float').count(), 0)
    await ann.locator(`[data-object="${box}"]`).focus()
    await ann.keyboard.press('Control+Alt+r') // over -> around
    await ann.waitForSelector('[data-testid=text] .wrap-float')
    await ann.waitForTimeout(600)
    assert.equal(await overlapping(ann, box, 8), 0, 'around: no word lies over the box')
    await ann.screenshot({ path: `${SHOTS}/wrap-around.png` })
    log2('around: ok')

    // ---- a picture and a shape, in the second and third paragraph: each goes into the text above and below the words,
    // and every one of the three keeps the words away from it (they are measured one after the other, in text order)
    const png = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
      'base64',
    )
    await ann.locator('[data-testid=text] [data-paragraph]').nth(1).click()
    await ann.keyboard.press('Home')
    await menu(ann, 'Edit', 'Image')
    await ann.setInputFiles('.modal input[type=file]', { name: 'dot.png', mimeType: 'image/png', buffer: png })
    await ann.fill('.modal .field input', 'A small picture')
    await ann.click('.modal button[type=submit]')
    await ann.waitForFunction(() => document.querySelectorAll('[data-testid=object-layer] [data-object]').length === 2)
    await ann.locator('[data-testid=text] [data-paragraph]').nth(2).click()
    await ann.keyboard.press('Home')
    await menu(ann, 'Edit', 'Rectangle')
    await ann.waitForFunction(() => document.querySelectorAll('[data-testid=object-layer] [data-object]').length === 3)
    await ann.waitForTimeout(800)
    const all = await objectIds(ann)
    assert.equal(all.length, 3)
    // the box is now around; the picture and the shape took the default
    const floats = await ann.locator('[data-testid=text] .wrap-float').count()
    assert.equal(floats, 3, 'each of the three takes room from the words')
    await ann.screenshot({ path: `${SHOTS}/wrap-three.png` })
    for (const id of all) assert.equal(await overlapping(ann, id, 8), 0, `no word lies over ${id}`)
    await ann.screenshot({ path: `${SHOTS}/wrap-three.png` })
    log2('a picture and a shape: ok')

    // ---- scrolled, they are still where the words keep away from them
    await ann.evaluate(() => (document.querySelector('.scroller').scrollTop = 150))
    await ann.waitForTimeout(600)
    for (const id of await objectIds(ann)) assert.equal(await overlapping(ann, id, 8), 0, `scrolled, no word lies over ${id}`)
    await ann.screenshot({ path: `${SHOTS}/wrap-scrolled.png` })
    await ann.evaluate(() => (document.querySelector('.scroller').scrollTop = 0))
    log2('scrolling: ok')

    // ---- and typing goes on: the words stay where they are, nothing of the boxes gets into the text
    await ann.locator('[data-testid=text] [data-paragraph]').nth(0).click()
    await ann.keyboard.press('Control+Home')
    await ann.keyboard.type('typed on ')
    for (let tries = 0; tries < 50 && !(await paragraphs(ann))[0].startsWith('typed on '); tries++) await ann.waitForTimeout(100)
    const text = await paragraphs(ann)
    assert.equal(text.length, 3)
    assert.ok(text[0].startsWith('typed on '), `what is typed lands in the words (${JSON.stringify(text.map((t) => t.slice(0, 30)))})`)
    assert.ok(!text.some((t) => /\u00a0|\ufffc/.test(t)), 'the boxes the lines go round are not text')
    await ann.waitForTimeout(500)
    for (const id of await objectIds(ann)) assert.equal(await overlapping(ann, id, 8), 0, `after typing, no word lies over ${id}`)
    log2('typing: ok')

    assert.deepEqual(ann.errors, [], 'no errors on the page')
    log2('ok')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error(e)
  process.exit(1)
})
