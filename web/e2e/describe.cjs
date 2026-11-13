// Alt text and the decorative mark on a picture in computes, from the keyboard (BITV 1.1.1):
// insert it described, step to it with Ctrl+Alt+PageDown, change the words with Ctrl+Alt+D, mark it decorative.
//   uv run python scripts/start.py --app computes --port 8765 --no-browser --rebuild --dir /tmp/claudia-axe
//   node e2e/describe.cjs        (CHROME=/path/to/chrome when playwright's own chromium is not installed)
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8765/'
const DOC = `alt-${Date.now() % 100000}`
const log = (...a) => console.log(...a)
// a 1x1 transparent PNG
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64')

;(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME, args: ['--no-sandbox'] })
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 800 } })).newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push('console: ' + m.text()))
  const picture = () => page.locator('[data-object]')
  try {
    await page.goto(URL)
    await page.fill('input[name=document]', DOC)
    await page.fill('input[name=user]', 'ann')
    await page.fill('input[name=password]', 'Ann-has-a-Password-1')
    await page.click('text=Create document')
    await page.waitForSelector('[data-testid=recovery-key]')
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
    await page.waitForSelector('[role=grid]')
    await page.waitForFunction(() => document.querySelector('.health.open'))

    // -- insert a picture: it cannot be inserted without words, unless it is marked as decoration
    await page.getByRole('menuitem', { name: 'Edit' }).click()
    await page.getByRole('menuitem', { name: 'Image…' }).click()
    await page.setInputFiles('.modal input[type=file]', { name: 'dot.png', mimeType: 'image/png', buffer: PNG })
    await page.waitForSelector('.modal .preview img')
    const insert = page.locator('.modal button[type=submit]')
    assert.equal(await insert.isDisabled(), true, 'no words, not decorative: not yet')
    await page.fill('.modal input[maxlength="300"]', 'a single dot')
    assert.equal(await insert.isDisabled(), false)
    await insert.click()
    await page.waitForSelector('[data-object]')
    assert.equal(await picture().getAttribute('role'), 'img')
    assert.equal(await picture().getAttribute('aria-label'), 'Picture: a single dot')

    // -- reach it with the keyboard and say something better
    await page.locator('[role=grid]').focus()
    await page.keyboard.press('Control+Alt+PageDown')
    await page.waitForSelector('[data-object].selected')
    await page.keyboard.press('Control+Alt+d')
    await page.waitForSelector('dialog[open] textarea')
    assert.equal(await page.inputValue('dialog textarea'), 'a single dot')
    await page.fill('dialog textarea', 'a tiny dark point, the start of the line')
    await page.click('dialog button[type=submit]')
    await page.waitForFunction(() => document.querySelector('[data-object]')?.getAttribute('aria-label') === 'Picture: a tiny dark point, the start of the line')

    // -- an empty description for a picture is refused, decorative is the way out
    await page.keyboard.press('Control+Alt+d')
    await page.waitForSelector('dialog[open] textarea')
    await page.fill('dialog textarea', '')
    assert.equal(await page.locator('dialog button[type=submit]').isDisabled(), true)
    await page.check('dialog input[type=checkbox]')
    assert.equal(await page.locator('dialog button[type=submit]').isDisabled(), false)
    await page.click('dialog button[type=submit]')
    await page.waitForFunction(() => document.querySelector('[data-object]')?.getAttribute('aria-hidden') === 'true')
    assert.equal(await picture().getAttribute('role'), 'presentation')
    assert.equal(await page.locator('[data-object]').getAttribute('aria-label'), null)

    // -- the same through the Format menu, and what a colleague or a later session finds: it is in the document
    await page.getByRole('menuitem', { name: 'Format' }).click()
    await page.getByRole('menuitem', { name: 'Describe Object…' }).click()
    await page.waitForSelector('dialog[open] textarea')
    assert.equal(await page.locator('dialog input[type=checkbox]').isChecked(), true)
    await page.keyboard.press('Escape')
    assert.deepEqual(errors, [])
    log('describe: ok')
  } catch (e) {
    await page.screenshot({ path: '/tmp/describe-fail.png' }).catch(() => undefined)
    console.error(e)
    process.exitCode = 1
  } finally {
    await browser.close()
  }
})()
