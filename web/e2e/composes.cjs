// Two people and the assistant in one text, in two real browser windows (server: --model claudia_composes:TextModel).
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8766/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `essay-${Date.now() % 100000}`
const ANN = ['ann', 'Ann has a password 1']
const BEN = ['ben', 'Ben has a password 1']

const log = (...a) => console.log(...a)

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
  [...document.querySelectorAll('[data-testid=text] [data-block]')].map((e) => {
    const copy = e.cloneNode(true)
    copy.querySelectorAll('[data-skip]').forEach((x) => x.remove())
    return copy.textContent
  })
const paragraphs = (page) => page.evaluate(textOf)
const INIT = `window.__text = ${textOf.toString()}`
const styles = (page) => page.$$eval('[data-testid=text] [data-block]', (els) => els.map((e) => e.className.replace(/.*st-(\S+).*/, '$1')))
async function waitFor(page, fn, arg, what) {
  try {
    await page.waitForFunction(fn, arg, { timeout: 8000 })
  } catch {
    throw new Error('timed out waiting for ' + what)
  }
}
async function waitParagraphs(page, expected, what) {
  const deadline = Date.now() + 8000
  let got = []
  while (Date.now() < deadline) {
    got = await paragraphs(page)
    if (JSON.stringify(got) === JSON.stringify(expected)) return
    await new Promise((r) => setTimeout(r, 100))
  }
  throw new Error(`${what}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(got)}`)
}
// A menu item by its path: `menu(page, 'File', 'Manage', 'Share')` opens File, then Manage ▸, then clicks Share….
async function menu(page, title, ...path) {
  await page.click(`.menus .title:text-is("${title}")`)
  for (const item of path) await page.click(`.menus .drop [role=menuitem]:has-text("${item}")`)
}

;(async () => {
  const browser = await chromium.launch()
  try {
    // ---- ann makes a text and writes
    const ann = await open(browser, ANN, true)
    assert.equal(await ann.locator('h1.doc').textContent(), DOC)
    assert.equal(await ann.evaluate(() => document.documentElement.dataset.app), 'composes')
    await ann.click('[data-testid=text]')
    await ann.keyboard.type('Why we write together')
    await ann.keyboard.press('Enter')
    await ann.keyboard.type('In order to recieve feedback we utilize teh crowd.')
    await ann.keyboard.press('Enter')
    await ann.keyboard.type('Second paragraph.')
    await ann.waitForTimeout(1200)
    await waitParagraphs(ann, ['Why we write together', 'In order to recieve feedback we utilize teh crowd.', 'Second paragraph.'], 'ann typed')
    log('ann typed three paragraphs')

    // a heading: the style of the first paragraph
    await ann.click('[data-testid=text] [data-block]:first-child')
    await ann.click('[data-testid=style-button]')
    await ann.click('[data-style=title]')
    await waitFor(ann, () => document.querySelector('[data-testid=text] h1'), null, 'a title')
    assert.deepEqual((await styles(ann)).slice(0, 2), ['title', 'body'])
    log('style set: title')

    // ---- ann lets ben in
    await menu(ann, 'File', 'Manage', 'Share')
    await ann.fill('.modal input >> nth=0', BEN[0])
    await ann.fill('.modal input >> nth=1', BEN[1])
    await ann.click('.modal button:has-text("Add person")')
    await ann.waitForSelector('.added')
    await ann.keyboard.press('Escape')

    const ben = await open(browser, BEN, false)
    await waitParagraphs(ben, ['Why we write together', 'In order to recieve feedback we utilize teh crowd.', 'Second paragraph.'], 'ben sees the text')
    assert.deepEqual((await styles(ben)).slice(0, 2), ['title', 'body'])
    log('ben sees the same text and the title style')

    // ---- both write at once, in different paragraphs
    const lastOf = (page) => page.locator('[data-testid=text] [data-block]').last()
    await lastOf(ann).click()
    await ann.keyboard.press('End')
    await ann.keyboard.type(' Ann adds this.')
    await ben.locator('[data-testid=text] [data-block]').nth(1).click()
    await ben.keyboard.press('Home')
    await ben.keyboard.type('Ben: ')
    await ann.waitForTimeout(1500)
    const expected = ['Why we write together', 'Ben: In order to recieve feedback we utilize teh crowd.', 'Second paragraph. Ann adds this.']
    await waitParagraphs(ann, expected, 'ann after both wrote')
    await waitParagraphs(ben, expected, 'ben after both wrote')
    log('both writers converged')

    // ben sees ann's caret, ann sees ben's
    await waitFor(ben, () => document.querySelector('.peer-caret b')?.textContent === 'ann', null, "ann's caret on ben's screen")
    await waitFor(ann, () => document.querySelector('.peer-caret b')?.textContent === 'ben', null, "ben's caret on ann's screen")
    log('carets seen')
    await ann.screenshot({ path: `${SHOTS}/c1-ann-two-writers.png` })

    // ---- authorship
    await ann.click('[data-testid=authors]')
    await waitFor(ann, () => document.querySelectorAll('.seg.by').length >= 3, null, 'authorship colours')
    const writers = await ann.$$eval('.seg.by', (els) => [...new Set(els.map((e) => e.title))])
    assert.ok(writers.includes('written by ann') && writers.includes('written by ben'), writers.join(' | '))
    log('authorship shown:', writers.join(', '))

    // ---- the assistant suggests, nothing is written until a person accepts
    const input = ann.locator('aside input').first()
    await input.fill('@ai review this text')
    await input.press('Enter')
    // The suggestions are marked in the text and counted in the bottom bar; a mark opens its card (no list in the panel).
    const marks = () => new Set([...document.querySelectorAll('[data-testid=text] [data-sug]')].map((m) => m.dataset.sug)).size >= 3
    await waitFor(ann, marks, null, 'the suggestions').catch(async (e) => {
      console.log('chat:', JSON.stringify(await ann.$$eval('.msg', (els) => els.map((x) => x.textContent.replace(/\s+/g, ' ').trim()))))
      throw e
    })
    const before = await paragraphs(ann)
    assert.ok(before[1].includes('recieve') && before[1].includes('utilize'), 'the text is untouched: ' + before[1])
    await waitFor(ben, () => new Set([...document.querySelectorAll('[data-testid=text] [data-sug]')].map((m) => m.dataset.sug)).size >= 3, null, 'the suggestions on ben\'s screen')
    assert.match(await ann.locator('[data-testid=open-suggestions]').innerText(), /^3 suggestions/)
    assert.equal(await ann.locator('[data-testid=suggestions]').count(), 0, 'no suggestion list above the panel tabs any more')
    log('assistant made suggestions; the text is untouched')
    await ann.screenshot({ path: `${SHOTS}/c2-suggestions.png` })

    // ben accepts the spelling fix, ann rejects "utilize"
    await ben.locator('[data-testid=text] [data-sug]:has-text("recieve")').first().click()
    const spelling = ben.locator('[data-testid=suggestion]:has-text("receive")')
    await spelling.waitFor()
    await ben.screenshot({ path: `${SHOTS}/c2b-suggestion-card.png` })
    await spelling.locator('button.accept').click()
    await waitFor(ben, () => window.__text().some((t) => t.includes('receive feedback')), null, 'the accepted word')
    await waitFor(ann, () => window.__text().some((t) => t.includes('receive feedback')), null, 'accepted word on ann\'s screen')
    await ann.locator('[data-testid=text] [data-sug]:has-text("utilize")').first().click()
    const reject = ann.locator('[data-testid=suggestion]:has-text("utilize")')
    await reject.waitFor()
    await reject.locator('button.reject').click()
    await waitFor(ann, () => ![...document.querySelectorAll('[data-testid=text] [data-sug]')].some((m) => m.textContent.includes('utilize')), null, 'rejected suggestion gone')
    assert.ok((await paragraphs(ann))[1].includes('utilize'), 'utilize stays')
    log('accepted one, rejected one')

    // accepted text belongs to ben, via ai
    const via = await ann.$$eval('.seg.via', (els) => els.map((e) => e.title))
    assert.ok(via.some((t) => t.includes('ben') && t.includes('ai')), 'via: ' + via.join(' | '))
    log('accepted text is ben\'s, through ai:', via.join(', '))

    // ---- undo takes back the accepted word (ben's own step)
    await ben.locator('[data-testid=text]').click()
    await ben.keyboard.press('Control+z')
    await waitFor(ann, () => window.__text().some((t) => t.includes('recieve feedback')), null, 'undo of the accept')
    log('ben undid the accept; ann sees it')

    // ---- page view and the shared shell
    await ann.click('[data-testid=page-view]')
    await waitFor(ann, () => document.querySelector('.scroller.page'), null, 'page view')
    await ann.screenshot({ path: `${SHOTS}/c3-page.png` })
    await ann.click('button:text-is("Flow")')

    for (const page of [ann, ben]) assert.deepEqual(page.errors, [], 'no errors on the pages: ' + page.errors.join(' | '))
    log('OK')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error('FAILED:', e.message)
  process.exit(1)
})
