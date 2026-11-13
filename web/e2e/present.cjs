// Presenter mode, in a real browser (E10.2): notes and a planned time per slide, the show with its audience view,
// presenter view, overview and blank screen, and the keys that start it (F5 and the Mac-safe chord). Start a
// presentation server first:
//   uv run python scripts/start.py creates --no-browser      (URL defaults to http://127.0.0.1:8765/; CI passes URL=)
// BROWSER=firefox runs it in Firefox (the owner's main browser); CHROME=/path/to/chrome uses a browser that is installed.
const { chromium, firefox } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8765/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `deck-show-${Date.now() % 100000}`
const log = (...a) => console.log(...a)

async function waitFor(page, fn, arg, what) {
  try {
    await page.waitForFunction(fn, arg, { timeout: 8000 })
  } catch {
    throw new Error('timed out waiting for ' + what)
  }
}
const show = (page) => page.locator('[data-testid=show]')
const text = (page, id) => page.locator(`[data-testid=${id}]`).first().innerText()

async function writeBox(page, words) {
  await page.click('[data-tool="text"]')
  const box = page.locator('.obj.text').last()
  await box.dblclick({ position: { x: 30, y: 30 } })
  await page.waitForSelector('textarea.editor')
  await page.keyboard.type(words)
  await page.keyboard.press('Enter')
  await waitFor(page, (w) => [...document.querySelectorAll('.obj.text')].some((e) => e.textContent.includes(w)), words, 'the words')
}

/** Write notes in the field under the slide and leave it (the change is written on leaving). */
async function writeNotes(page, notes) {
  await page.fill('[data-testid=notes-field]', notes)
  await page.click('[data-testid=slide]', { position: { x: 5, y: 5 } })
  await page.waitForTimeout(400)
}
async function planTime(page, typed) {
  await page.click('[data-testid=time-chip]')
  await page.fill('[data-testid=time-field]', typed)
  await page.keyboard.press('Enter')
  await page.keyboard.press('Escape')
  await page.waitForTimeout(300)
}

;(async () => {
  const type = process.env.BROWSER === 'firefox' ? firefox : chromium
  const browser = await type.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {})
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

    // ---- two slides, each with words, notes and a time
    await writeBox(page, 'Welcome')
    await writeNotes(page, 'Say **hello** first\n- point *one*\n- point two')
    await planTime(page, '2')
    assert.match(await text(page, 'time-chip'), /2:00/)
    await page.click('button[aria-label="new slide"]')
    await waitFor(page, () => document.querySelectorAll('[aria-label=slides] [role=tab]').length === 2, null, 'a second slide')
    await writeBox(page, 'The numbers')
    await writeNotes(page, 'Slow down here')
    await planTime(page, '90s')
    assert.match(await text(page, 'time-chip'), /1:30/)
    await page.click('[aria-label=slides] [role=tab]:has-text("Slide 1")')
    await waitFor(page, () => document.querySelector('[data-testid=notes-field]').value.includes('hello'), null, 'the notes of slide 1')
    assert.match(await text(page, 'plan-total'), /3:30/)
    assert.match(await page.locator('[aria-label=slides] [role=tab]').first().innerText(), /2:00/)
    log('notes and a time on both slides; the bar adds them up to 3:30')

    // ---- the show: the button starts it from the first slide, the audience view fills the window
    await page.click('[data-tool="present"]')
    await show(page).waitFor()
    assert.equal(await show(page).getAttribute('data-view'), 'audience')
    assert.equal(await show(page).getAttribute('data-index'), '0')
    assert.match(await text(page, 'show-announce'), /Slide 1 of 2/)
    await page.keyboard.press('ArrowRight')
    assert.equal(await show(page).getAttribute('data-index'), '1')
    assert.match(await text(page, 'show-announce'), /Slide 2 of 2: The numbers/)
    await page.screenshot({ path: `${SHOTS}/present-audience.png` })
    log('the audience view opens on slide 1 and → goes on, announced for a screen reader')

    // ---- the keys of the editor do nothing while the show runs
    const before = await page.locator('[data-testid=show-position]').first().innerText()
    await page.keyboard.press('Control+z')
    await page.keyboard.press('Delete')
    assert.equal(await page.locator('[data-testid=show-position]').first().innerText(), before)

    // ---- the presenter view: notes formatted, the clock, this slide against its plan
    await page.keyboard.press('p')
    await page.locator('[data-testid=presenter]').waitFor()
    assert.match(await text(page, 'presenter'), /Slow down here/)
    assert.match(await text(page, 'show-elapsed'), /3:30/)
    assert.match(await text(page, 'show-slide-time'), /1:30/)
    await page.keyboard.press('ArrowLeft')
    await waitFor(page, () => document.querySelector('[data-testid=presenter] .notes-body strong'), null, 'the bold word in the notes')
    assert.equal(await page.locator('.notes-body strong').innerText(), 'hello')
    assert.equal(await page.locator('.notes-body em').innerText(), 'one')
    assert.equal(await page.locator('.notes-body strong').evaluate((e) => e.tagName), 'STRONG')
    await page.screenshot({ path: `${SHOTS}/present-presenter.png` })
    log('P swaps to the presenter view: notes in Markdown, elapsed against 3:30, this slide against 2:00')

    // ---- the overview picks a slide by a typed number; B blanks; Esc steps back out one layer at a time
    await page.keyboard.press('g')
    await page.locator('[data-testid=show-overview]').waitFor()
    await page.keyboard.press('2')
    await page.keyboard.press('Enter')
    await waitFor(page, () => document.querySelector('[data-testid=show]').dataset.index === '1', null, 'slide 2 by number')
    assert.equal(await page.locator('[data-testid=show-overview]').count(), 0)
    await page.keyboard.press('p')
    await page.keyboard.press('b')
    await page.locator('[data-testid=show-blank]').waitFor()
    await page.keyboard.press('b')
    assert.equal(await page.locator('[data-testid=show-blank]').count(), 0)
    await page.keyboard.press('ArrowRight')
    await page.locator('[data-testid=show-end]').waitFor()
    await page.keyboard.press('Escape')
    await show(page).waitFor({ state: 'detached' })
    log('G, a typed number and Enter jump; B blanks and unblanks; → past the last slide shows the end; Esc leaves')

    // ---- the keys: F5 (and it does not reload), Shift+F5 from this slide, the Mac-safe chord by physical key
    await page.click('[aria-label=slides] [role=tab]:has-text("Slide 2")')
    await page.locator('[data-testid=slide]').click({ position: { x: 5, y: 5 } })
    await page.keyboard.press('F5')
    await show(page).waitFor()
    assert.equal(await show(page).getAttribute('data-index'), '0', 'F5 starts at the first slide')
    await page.keyboard.press('Escape')
    await show(page).waitFor({ state: 'detached' })
    await page.keyboard.press('Shift+F5')
    await show(page).waitFor()
    assert.equal(await show(page).getAttribute('data-index'), '1', 'Shift+F5 starts at this slide')
    await page.keyboard.press('Escape')
    await show(page).waitFor({ state: 'detached' })
    await page.keyboard.press('Control+Alt+KeyP')
    await show(page).waitFor()
    assert.equal(await show(page).getAttribute('data-index'), '0')
    await page.keyboard.press('Escape')
    await show(page).waitFor({ state: 'detached' })
    // F5 in the notes field starts the show too, and does not reload the page
    await page.click('[data-testid=notes-field]')
    await page.keyboard.press('F5')
    await show(page).waitFor()
    await page.keyboard.press('Escape')
    await show(page).waitFor({ state: 'detached' })
    log('F5, Shift+F5 and Ctrl+Alt+P (the chord a Mac keyboard can send) all start the show')

    // ---- the View menu names the keys and starts it too
    await page.click('.menus .title:text-is("View")')
    assert.match(await page.locator('.menus .drop [role^=menuitem]:has-text("Present from the first slide")').innerText(), /F5/)
    await page.click('.menus .drop [role^=menuitem]:has-text("Present from this slide")')
    await show(page).waitFor()
    await page.keyboard.press('Escape')
    await show(page).waitFor({ state: 'detached' })

    // ---- the document is as it was: showing writes nothing (D340)
    assert.match(await text(page, 'plan-total'), /3:30/)

    assert.deepEqual(errors, [])
    console.log('\nALL GOOD')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error('FAILED:', e)
  process.exit(1)
})
