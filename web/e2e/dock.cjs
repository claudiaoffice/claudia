// The dock in a real browser (D550, D551, D553): things have names, a tag in the chat points at one, and the history can
// be replayed. Two people in one presentation:
//   - a new presentation's slides have names of their own, and the tabs show two different ones (before 2026-11-15 the
//     first slide had none, its tab said "Slide 1" by its place, and the next slide was named "Slide 1" too);
//   - ann renames a slide (Edit ▸ Rename Slide…), writes "#" in the chat, picks it from the list and
//     sends the message; ben clicks the tag and is taken to that slide;
//   - ann renames it again, and the tag in ben's chat shows the new name (a tag holds the id, not the words);
//   - ann replays the history: the replay bar comes, the slide cannot be changed while it is shown, and "Back to now"
//     ends it.
// Start a presentation server first (as CI does): python -m claudia_server --model claudia_creates:SlideModel ...
// Run: URL=http://127.0.0.1:8767/ npm run e2e:dock
const { chromium } = require('playwright')
const assert = require('node:assert/strict')
const fs = require('node:fs')

const URL = process.env.URL ?? 'http://127.0.0.1:8767/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `dock-${Date.now() % 100000}`
const ANN = ['ann', 'Ann has a password 1']
const BEN = ['ben', 'Ben has a password 1']
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
  await page.click(create ? 'text=Create document' : 'button:text-is("Open")')
  if (create) {
    await page.waitForSelector('[data-testid=recovery-key]')
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
  }
  await page.waitForSelector('[data-testid=slide]')
  await page.waitForFunction(() => document.querySelector('.health.open'))
  return page
}

async function waitFor(page, fn, arg, what) {
  try {
    await page.waitForFunction(fn, arg, { timeout: 8000 })
  } catch {
    throw new Error('timed out waiting for ' + what)
  }
}

const tabs = (page) => page.$$eval('[aria-label=slides] [role=tab]', (els) => els.map((e) => e.childNodes[0].textContent.trim()))
const activeTab = (page) => page.$eval('[aria-label=slides] [role=tab][aria-selected=true]', (e) => e.childNodes[0].textContent.trim())
const chatBox = '.write [role=combobox]'

async function rename(page, slideIndex, name) {
  await page.click(`[aria-label=slides] [role=tab] >> nth=${slideIndex}`)
  await page.click('.menus .title:text-is("Edit")')
  await page.click('.menus .drop [role=menuitem]:has-text("Rename Slide")')
  await page.waitForSelector('.modal input')
  await page.fill('.modal input', name)
  await page.press('.modal input', 'Enter')
  await waitFor(page, ([i, n]) => document.querySelectorAll('[aria-label=slides] [role=tab]')[i]?.textContent.includes(n), [slideIndex, name], `the tab to say ${name}`)
}

;(async () => {
  fs.mkdirSync(SHOTS, { recursive: true })
  const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {})
  try {
    const ann = await open(browser, ANN, true)
    await ann.click('[aria-label="new slide"]')
    await waitFor(ann, () => document.querySelectorAll('[aria-label=slides] [role=tab]').length === 2, null, 'a second slide')
    const named = await tabs(ann)
    assert.equal(new Set(named).size, 2, `two slides, two names: ${named.join(' | ')}`)
    log('two slides with two names:', named.join(', '))

    // ---- a name, and a tag to it in the chat
    await rename(ann, 1, 'Results')
    await ann.click(chatBox) // "#" offers the things in sight: the slide shown and what is on it (D551)
    await ann.keyboard.type('Look at #Res')
    await ann.waitForSelector('#tag-list [role=option]:has-text("Results")')
    await ann.keyboard.press('Enter')
    await waitFor(ann, (sel) => document.querySelector(sel)?.querySelector('.chip'), chatBox, 'a chip in the chat box')
    await ann.keyboard.type(' please')
    await ann.keyboard.press('Enter')
    await ann.waitForSelector('.msg button.tag:text-is("#Results")')
    log('ann sent a message with a tag to the slide “Results”')

    // ---- ben follows it
    await ann.click('.menus .title:text-is("File")')
    await ann.click('.menus .drop [role=menuitem]:has-text("Manage")')
    await ann.click('.menus .drop [role=menuitem]:has-text("Share")')
    await ann.fill('.modal input >> nth=0', BEN[0])
    await ann.fill('.modal input >> nth=1', BEN[1])
    await ann.click('.modal button:has-text("Add person")')
    await ann.waitForSelector('.added')
    await ann.keyboard.press('Escape')
    const ben = await open(browser, BEN, false)
    assert.equal(await activeTab(ben), (await tabs(ben))[0], 'ben starts on the first slide')
    await ben.click('.msg button.tag:text-is("#Results")')
    await waitFor(ben, () => document.querySelector('[aria-label=slides] [role=tab][aria-selected=true]')?.textContent.includes('Results'), null, 'ben taken to “Results”')
    log('ben clicked the tag and is on “Results”')

    // ---- a rename does not break the tag
    await rename(ann, 1, 'Findings')
    await ben.waitForSelector('.msg button.tag:text-is("#Findings")')
    log('after the rename ben’s tag says “#Findings”')

    // ---- replay
    await ann.click('button.replayBtn')
    await ann.waitForSelector('[data-testid=replay-bar]')
    await ann.waitForFunction(() => document.querySelector('aside.panel')?.classList.contains('replaying'))
    assert.equal(await ann.locator('[aria-label="new slide"]').count(), 0, 'nothing can be added while the past is shown')
    await ann.screenshot({ path: `${SHOTS}/dock-replay.png` })
    await ann.click('button.replayBtn:text-is("Back to now")')
    await waitFor(ann, () => !document.querySelector('[data-testid=replay-bar]'), null, 'the replay to end')
    assert.equal(await ann.locator('[aria-label="new slide"]').count(), 1, 'back in the present, slides can be added again')
    log('replay started, showed the past read-only, and ended')

    const errors = [...ann.errors, ...ben.errors]
    assert.deepEqual(errors, [], errors.join('\n'))
    console.log('\nALL GOOD')
  } catch (error) {
    console.error('FAILED:', error.message)
    process.exitCode = 1
  } finally {
    await browser.close()
  }
})()
