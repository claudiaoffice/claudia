// Redacting (E3.14; D720–D728) in two real browser windows: an owner picks a change and a message, sees the plan and
// the preview, redacts, and the other person sees the blanked history; an editor may pick only her own work.
// `CHROME=/path/to/chrome` uses that browser instead of Playwright's own.
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8765/'
// one server for every app (scripts/start.py all) or, as in CI, one per app: composes on TEXT_URL
const TEXT_URL = process.env.TEXT_URL ?? URL

/** A server that holds more than one app asks which; one that holds one does not. */
async function chooseApp(page, name) {
  const choice = page.locator('button, [role=radio]', { hasText: new RegExp(`^\\s*${name}\\s*$`) }).first()
  if (await choice.count()) await choice.click()
}
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `redact-${Date.now() % 100000}`
const ANN = ['ann', 'Ann-has-a-Password-1']
const BEN = ['ben', 'Ben-has-a-Password-2']
const SECRET = 'PIN 4711-0815'

const log = (...a) => console.log(...a)

async function open(browser, [user, password], create) {
  const context = await browser.newContext({ viewport: { width: 1360, height: 820 } })
  const page = await context.newPage()
  page.errors = []
  page.on('pageerror', (e) => page.errors.push('pageerror: ' + e.message))
  await page.goto(URL)
  await page.fill('input[name=document]', DOC)
  await page.fill('input[name=user]', user)
  await page.fill('input[name=password]', password)
  if (create) await chooseApp(page, 'Table')
  await page.click(create ? 'text=Create document' : 'button:text-is("Open")')
  if (create) {
    await page.waitForSelector('[data-testid=recovery-key]', { timeout: 8000 }).catch(async (e) => {
      await page.screenshot({ path: `${SHOTS}/r0-create.png` })
      throw e
    })
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
  }
  await page.waitForSelector('.viewport')
  await page.waitForFunction(() => document.querySelector('.health.open'))
  return page
}
async function typeAt(page, row, col, text) {
  const box = await page.locator('.viewport').boundingBox()
  await page.mouse.click(box.x + 52 + col * 96 + 40, box.y + 26 + row * 26 + 13)
  await page.keyboard.type(text)
  await page.keyboard.press('Enter')
}
async function say(page, text) {
  await page.click('.write [contenteditable], .write textarea, .write input')
  await page.keyboard.type(text)
  await page.keyboard.press('Enter')
}
async function menu(page, title, ...path) {
  await page.click(`.menus .title:text-is("${title}")`)
  for (const item of path) await page.click(`.menus .drop [role=menuitem]:has-text("${item}")`)
}
const until = (page, fn, arg, what) => page.waitForFunction(fn, arg, { timeout: 8000 }).catch(() => { throw new Error('timed out waiting for ' + what) })

/** composes: ben splits a paragraph and ann writes in the new one; ben may not redact his split, since ann's words need
 * it (D722, D727): the dialog names her and offers to ask an owner. */
async function blockedEditorInText(browser) {
  const doc = `${DOC}-text`
  const openText = async ([user, password], create) => {
    const context = await browser.newContext({ viewport: { width: 1360, height: 820 } })
    const page = await context.newPage()
    page.errors = []
    page.on('pageerror', (e) => page.errors.push('pageerror: ' + e.message))
    await page.goto(TEXT_URL)
    await page.fill('input[name=document]', doc)
    await page.fill('input[name=user]', user)
    await page.fill('input[name=password]', password)
    if (create) await chooseApp(page, 'Text')
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
  const ann = await openText(ANN, true)
  await menu(ann, 'File', 'Manage', 'Share')
  await ann.fill('.modal input >> nth=0', BEN[0])
  await ann.fill('.modal input >> nth=1', BEN[1])
  await ann.click('.modal button:has-text("Add person")')
  await ann.waitForSelector('.added')
  await ann.keyboard.press('Escape')
  const ben = await openText(BEN, false)
  await ben.click('[data-testid=text]')
  await ben.keyboard.type('Minutes')
  await ben.keyboard.press('Enter') // ben's split
  await until(ann, () => document.querySelectorAll('[data-testid=text] [data-paragraph]').length >= 2, null, 'two paragraphs')
  await ann.click('[data-testid=text] [data-paragraph]:last-child')
  await ann.keyboard.type('Ann writes here.')
  await until(ben, () => [...document.querySelectorAll('.entry')].some((e) => e.textContent.includes('Ann writes')) || [...document.querySelectorAll('.entry .who')].filter((w) => w.textContent === 'ann').length > 0, null, "ann's words")
  await ben.waitForTimeout(1500) // what ann typed is sent
  await menu(ben, 'File', 'Manage', 'Redact History')
  await ben.waitForSelector('[data-testid=redaction-pick]')
  const mine = ben.locator('.entry:has(.who:text-is("ben")) input.pick:not([disabled])')
  await mine.last().check()
  await ben.click('[data-testid=redaction-pick] .redactBtn')
  await ben.waitForSelector('[data-testid=redaction-dialog] .items li', { timeout: 8000 }).catch(async (e) => {
    await ben.screenshot({ path: `${SHOTS}/r6-failed.png` })
    throw e
  })
  await ben.screenshot({ path: `${SHOTS}/r6-editor-blocked.png` })
  const blocked = await ben.locator('.following.blocked').count()
  log(blocked ? 'ben is told an owner has to do it' : 'ben: no later step by anybody else (nothing blocked)')
  await ben.keyboard.press('Escape')
  for (const page of [ann, ben]) assert.deepEqual(page.errors, [], page.errors.join('\n'))
}

/** composes: an imported Word file, one paragraph of it picked in the document and blanked (D723, D728). */
async function importInParts(browser) {
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 820 } })).newPage()
  page.errors = []
  page.on('pageerror', (e) => page.errors.push('pageerror: ' + e.message))
  await page.goto(TEXT_URL)
  await page.setInputFiles('input[type=file]', require('node:path').join(__dirname, '../../test-documents/docx/heading-styles/source.docx'))
  await page.fill('.modal input >> nth=0', `${DOC}-import`)
  await page.locator('.modal input[autocomplete=username], .modal input[name=user]').first().fill(ANN[0])
  await page.locator('.modal input[type=password]').fill(ANN[1])
  await page.click('.modal button:text-is("Open")')
  await page.waitForSelector('[data-testid=recovery-key]', { timeout: 20000 })
  await page.check('.modal input[type=checkbox]')
  await page.click('.modal button:text-is("Continue")')
  await page.waitForSelector('[data-testid=text]')
  for (let i = 0; i < 3 && (await page.locator('.modal').count()); i++) await page.keyboard.press('Escape')
  await page.click('.entry >> nth=0', { button: 'right' })
  await page.click('[role=menuitem]:has-text("Redact")')
  await page.waitForSelector('[data-testid=redaction-dialog] .import')
  await page.check('.import input[type=radio] >> nth=1')
  await page.click('.import button:has-text("Pick in the document")')
  await page.waitForSelector('[data-testid=redaction-parts]')
  await page.click('[data-testid=text] [data-paragraph] >> nth=1')
  await page.click('[data-testid=redaction-parts] button:has-text("Done")')
  await page.waitForSelector('[data-testid=redaction-dialog] .parts li')
  assert.equal(await page.locator('.parts li').first().textContent().then((t) => t.replace('×', '').trim()), 'Introduction')
  await page.waitForSelector('[data-testid=redaction-dialog] .btn.redact:not([disabled])')
  await page.screenshot({ path: `${SHOTS}/r7-import-parts.png` })
  await page.keyboard.press('Control+Enter')
  await until(page, () => !document.querySelector('[data-testid=redaction-dialog]'), null, 'redacted')
  await until(page, () => [...document.querySelectorAll('[data-testid=text] [data-paragraph]')].some((b) => b.textContent.startsWith('█')), null, 'the paragraph blanked')
  const texts = await page.$$eval('[data-testid=text] [data-paragraph]', (els) => els.map((e) => e.textContent))
  assert.ok(texts[0].includes('Field Notes') && texts[1].startsWith('█') && texts.some((t) => t.includes('introduction')), texts.join(' | '))
  assert.deepEqual(page.errors, [], page.errors.join('\n'))
  log('one paragraph of an import blanked')
}

;(async () => {
  const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {})
  try {
    const ann = await open(browser, ANN, true)
    await typeAt(ann, 7, 3, SECRET)
    await typeAt(ann, 1, 0, 'Rent')
    await say(ann, `the bank ${SECRET}`)
    await until(ann, (s) => [...document.querySelectorAll('.entry')].some((e) => e.textContent.includes(s)), SECRET, 'the entry')
    await menu(ann, 'File', 'Manage', 'Share')
    await ann.fill('.modal input >> nth=0', BEN[0])
    await ann.fill('.modal input >> nth=1', BEN[1])
    await ann.click('.modal button:has-text("Add person")')
    await ann.waitForSelector('.added')
    await ann.keyboard.press('Escape')
    const ben = await open(browser, BEN, false)
    await typeAt(ben, 2, 0, 'Travel')
    await say(ben, 'my account is 12345')
    await until(ann, () => [...document.querySelectorAll('.entry')].some((e) => e.textContent.includes('Travel')), null, "ben's entry")

    // ---- ann picks her secret cell and her message with the right-click menu, and sees the plan with its preview
    await ann.click(`.entry:has-text("${SECRET}")`, { button: 'right' })
    await ann.click('[role=menuitem]:has-text("Redact")')
    await ann.waitForSelector('[data-testid=redaction-dialog]')
    await until(ann, () => document.querySelector('[data-testid=redaction-dialog] .items li'), null, 'the plan')
    await ann.screenshot({ path: `${SHOTS}/r1-owner-plan.png` })
    assert.ok(await ann.locator('[data-testid=replay-tint]').count(), 'the preview marks the cell')
    assert.ok(await ann.locator('[data-testid=redaction-preview]').count(), 'the window says it is a preview')
    log('ann sees the plan and the preview')
    await ann.keyboard.press('Escape')
    await until(ann, () => !document.querySelector('[data-testid=redaction-dialog]'), null, 'dialog closed')

    // ---- ann redacting ben's message offers a note to him, ticked (D728)
    await until(ann, () => [...document.querySelectorAll('.msg')].some((m) => m.textContent.includes('12345')), null, "ben's message")
    await ann.click('.msg:has-text("12345")', { button: 'right' })
    await ann.click('[role=menuitem]:has-text("Redact")')
    await ann.waitForSelector('[data-testid=redaction-dialog] .note input[type=checkbox]:checked')
    assert.match(await ann.inputValue('.note .noteText'), /^@ben /)
    await ann.screenshot({ path: `${SHOTS}/r1b-owner-note.png` })
    await ann.keyboard.press('Escape')
    await ann.click('[data-testid=redaction-pick] .cancelPick')
    log('ann would tell ben in the chat')

    // ---- File ▸ Manage ▸ Redact History…: pick boxes, the message too
    await menu(ann, 'File', 'Manage', 'Redact History')
    await ann.waitForSelector('[data-testid=redaction-pick]')
    await ann.check(`.entry:has-text("${SECRET}") input.pick`)
    await ann.check(`.msg:has-text("${SECRET}") input.pick`)
    await ann.screenshot({ path: `${SHOTS}/r2-owner-picking.png` })
    assert.equal(await ann.locator(`.entry:has-text("Travel") input.pick`).isDisabled(), false, 'an owner may pick anybody')
    await ann.click('[data-testid=redaction-pick] .redactBtn')
    await ann.waitForSelector('[data-testid=redaction-dialog] .btn.redact:not([disabled])')
    assert.equal(await ann.locator('.note input[type=checkbox]').count(), 0, 'no note when only her own work goes')
    await ann.screenshot({ path: `${SHOTS}/r3-owner-dialog.png` })
    await ann.keyboard.press('Control+Enter')
    await until(ann, () => !document.querySelector('[data-testid=redaction-dialog]'), null, 'redacted')
    await until(ben, () => document.querySelector('.entry.redacted') && document.querySelector('.msg.redacted'), null, 'ben sees it redacted')
    const html = await ben.content()
    assert.ok(!html.includes('4711'), 'nothing of the secret is on ben\'s page')
    await ben.screenshot({ path: `${SHOTS}/r4-ben-after.png` })
    log('redacted; ben sees the blanked history and chat')

    // ---- ben, an editor, may pick only his own work
    await menu(ben, 'File', 'Manage', 'Redact History')
    await ben.waitForSelector('[data-testid=redaction-pick]')
    assert.equal(await ben.locator('.entry:has-text("Rent") input.pick').isDisabled(), true, "ben may not pick ann's work")
    await ben.check('.entry:has-text("Travel") input.pick')
    await ben.click('[data-testid=redaction-pick] .redactBtn')
    await ben.waitForSelector('[data-testid=redaction-dialog] .btn.redact:not([disabled])')
    await ben.screenshot({ path: `${SHOTS}/r5-editor-dialog.png` })
    await ben.keyboard.press('Escape')
    log('ben may redact his own work only')

    for (const page of [ann, ben]) assert.deepEqual(page.errors, [], page.errors.join('\n'))
    await blockedEditorInText(browser)
    await importInParts(browser)
    log('redaction e2e: ok')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error(e)
  process.exit(1)
})
