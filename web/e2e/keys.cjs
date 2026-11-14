// One key table for every app and client, and a new document with nothing to undo (UX-33, UX-35, UX-36; D360-D362),
// in a real browser against the three servers of `scripts/start.py all`:
//   uv run python scripts/start.py all --no-browser
//   node e2e/keys.cjs        (COMPUTES, COMPOSES, CREATES are the three addresses; the defaults are those of `all`)
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const COMPUTES = process.env.COMPUTES ?? 'http://127.0.0.1:8765/'
const COMPOSES = process.env.COMPOSES ?? 'http://127.0.0.1:8766/'
const CREATES = process.env.CREATES ?? 'http://127.0.0.1:8767/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `keys-${Date.now() % 100000}`
const log = (...a) => console.log(...a)

async function create(browser, url) {
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 800 } })).newPage()
  await page.goto(url)
  await page.fill('input[name=document]', DOC)
  await page.fill('input[name=user]', 'ann')
  await page.fill('input[name=password]', 'Ann has a password 1')
  await page.click('text=Create document')
  await page.waitForSelector('[data-testid=recovery-key]')
  await page.check('.modal input[type=checkbox]')
  await page.click('.modal button:text-is("Continue")')
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
/** The key a menu shows beside an entry. */
async function hint(page, title, label) {
  await page.click(`.menus .title:text-is("${title}")`)
  const text = await page.locator(`.menus .drop [role=menuitem]:has-text("${label}") kbd`).first().textContent()
  await page.keyboard.press('Escape')
  return text
}
const panelShown = (page) => page.evaluate(() => {
  const panel = document.querySelector('[data-region=panel]')
  return !!panel && panel.getBoundingClientRect().width > 0
})

;(async () => {
  const browser = await chromium.launch(process.env.CLAUDIA_CHROMIUM ? { executablePath: process.env.CLAUDIA_CHROMIUM } : {})
  try {
    // ---- computes: the first sheet is there and stays there; keys from the table
    const sheet = await create(browser, COMPUTES)
    await sheet.waitForSelector('.viewport')
    assert.equal(await sheet.locator('.footer [role=tab], .tabs [role=tab]').count() > 0 || (await sheet.locator('text=Sheet1').count()) > 0, true)
    await sheet.keyboard.press('Control+z')
    await sheet.waitForTimeout(500)
    assert.equal(await sheet.locator('text=This document has no sheet yet.').count(), 0, 'Ctrl+Z took the first sheet away')
    log('computes: a new workbook has Sheet1, and Ctrl+Z leaves it')
    assert.equal(await hint(sheet, 'Edit', 'Image…'), 'Ctrl+Alt+I')
    assert.equal(await hint(sheet, 'Tools', 'Names…'), 'Ctrl+F3')
    assert.equal(await hint(sheet, 'File', 'Open…'), 'Ctrl+O')
    log('computes: the menus show the keys of the table')
    assert.equal(await panelShown(sheet), true)
    await sheet.keyboard.press('Control+Alt+h')
    await waitFor(sheet, () => { const p = document.querySelector('[data-region=panel]'); return !p || p.getBoundingClientRect().width === 0 }, null, 'the panel to hide')
    await sheet.keyboard.press('Control+Alt+h')
    await waitFor(sheet, () => { const p = document.querySelector('[data-region=panel]'); return !!p && p.getBoundingClientRect().width > 0 }, null, 'the panel to come back')
    log('computes: Ctrl+Alt+H hides and shows History and Chat')
    await sheet.keyboard.press('Control+F3')
    await waitFor(sheet, () => !!document.querySelector('dialog[open], .modal'), null, 'Names… to open')
    await sheet.screenshot({ path: `${SHOTS}/keys-computes-names.png` })
    await sheet.keyboard.press('Escape')
    log('computes: Ctrl+F3 opens Names…')

    // the grid has its own arrow keys: Alt+Shift+↑ must still reach Edit ▸ Row ▸ Insert Above
    const box = await sheet.locator('.viewport').boundingBox()
    await sheet.mouse.click(box.x + 52 + 40, box.y + 26 + 13)
    await sheet.keyboard.type('first')
    await sheet.keyboard.press('Enter')
    await sheet.mouse.click(box.x + 52 + 40, box.y + 26 + 13)
    await sheet.keyboard.press('Alt+Shift+ArrowUp')
    await waitFor(sheet, () => [...document.querySelectorAll('.cell:not(.blank)')].some((c) => c.textContent.trim() === 'first' && c.getAttribute('aria-rowindex') !== '2' && (c.closest('[role=row]')?.getAttribute('aria-rowindex') ?? '') === '3'), null, 'the row to move down by one')
    log('computes: Alt+Shift+↑ inserts a row above, from the grid')

    // ---- composes: nothing to undo in a new text; the List flyout and Insert have their keys
    const text = await create(browser, COMPOSES)
    await text.waitForSelector('[data-testid=text]')
    await text.click('.menus .title:text-is("Edit")')
    const undo = text.locator('.menus .drop [role=menuitem]:has-text("Undo")').first()
    assert.equal(await undo.isDisabled(), true, 'a new text has something to undo')
    await text.keyboard.press('Escape')
    log('composes: a new text has nothing to undo')
    assert.equal(await hint(text, 'File', 'Print…'), 'Ctrl+P')
    await text.click('.menus .title:text-is("Format")')
    await text.click('.menus .drop [role=menuitem]:has-text("List")')
    assert.equal(await text.locator('.menus .drop.sub [role=menuitemcheckbox]:has-text("Bulleted List") kbd').textContent(), 'Ctrl+Shift+8')
    await text.keyboard.press('Escape')
    await text.keyboard.press('Escape')
    log('composes: File ▸ Print… and Format ▸ List ▸ show their keys')
    await text.keyboard.press('Control+?')
    await waitFor(text, () => !!document.querySelector('dialog[open], .modal'), null, 'Config ▸ Shortcuts to open')
    await text.screenshot({ path: `${SHOTS}/keys-composes-shortcuts.png` })
    await text.keyboard.press('Escape')
    log('composes: Ctrl+? opens the shortcuts')

    // ---- creates: Ctrl+M is a new slide; Show Grid is after the shared View entries
    const deck = await create(browser, CREATES)
    await deck.waitForSelector('[aria-label=slides] [role=tab]')
    await deck.click('.menus .title:text-is("Edit")') // (the canvas, not a text field, has the keys)
    await deck.keyboard.press('Escape')
    await deck.keyboard.press('Control+m')
    await waitFor(deck, () => document.querySelectorAll('[aria-label=slides] [role=tab]').length === 2, null, 'Ctrl+M to add a slide')
    log('creates: Ctrl+M adds a slide')
    await deck.click('.menus .title:text-is("View")')
    const view = await deck.$$eval('.menus .drop [role=menuitem], .menus .drop [role=menuitemcheckbox]', (els) => els.map((e) => e.querySelector('.label')?.textContent?.trim()))
    await deck.keyboard.press('Escape')
    assert.deepEqual(view, ['Show Who Wrote What', 'History and Chat', 'Dark Mode', 'Show Grid'])
    log('creates: View ▸ Show Grid follows the shared entries')
    console.log('\nALL GOOD')
  } catch (error) {
    console.error('FAILED:', error.message)
    process.exitCode = 1
  } finally {
    await browser.close()
  }
})()
