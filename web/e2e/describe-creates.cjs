// Alt text and the decorative mark on a slide's picture (BITV 1.1.1): inserted decorative, then described from the
// object's context menu, then back to decorative with Ctrl+Alt+D.
//   uv run python -m claudia_server --no-tls --model claudia_creates:SlideModel --port 8767 --web web/.output/public --dir /tmp/claudia-axe2
//   node e2e/describe-creates.cjs        (CLAUDIA_CHROMIUM=/path/to/chrome when playwright's own chromium is not installed)
const { launch } = require('./browser.cjs')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8767/'
const DOC = `alt-slides-${Date.now() % 100000}`
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64')

;(async () => {
  const browser = await launch()
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 800 } })).newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push('console: ' + m.text()))
  const picture = () => page.locator('.obj.image')
  try {
    await page.goto(URL)
    await page.fill('input[name=document]', DOC)
    await page.fill('input[name=user]', 'ann')
    await page.fill('input[name=password]', 'Ann-has-a-Password-1')
    await page.click('text=Create document')
    await page.waitForSelector('[data-testid=recovery-key]')
    await page.check('.modal input[type=checkbox]')
    await page.click('.modal button:text-is("Continue")')
    await page.waitForSelector('[data-testid=slide]')
    await page.waitForFunction(() => document.querySelector('.health.open'))

    await page.getByRole('menuitem', { name: 'Edit' }).click()
    await page.getByRole('menuitem', { name: 'Image…' }).click()
    await page.setInputFiles('.modal input[type=file]', { name: 'dot.png', mimeType: 'image/png', buffer: PNG })
    await page.waitForSelector('.modal .preview img')
    const insert = page.locator('.modal button[type=submit]')
    assert.equal(await insert.isDisabled(), true)
    await page.check('.modal input[type=checkbox]')
    assert.equal(await page.locator('.modal input[maxlength="300"]').isDisabled(), true, 'a decoration has no words to type')
    await insert.click()
    await picture().waitFor()
    assert.equal(await picture().getAttribute('aria-label'), 'Picture (decorative)')

    // the object's own menu offers it, with its key
    await picture().click({ button: 'right' })
    await page.getByRole("menuitem", { name: /describe…/i }).click()
    await page.waitForSelector('dialog[open] textarea')
    assert.equal(await page.locator('dialog input[type=checkbox]').isChecked(), true)
    await page.uncheck('dialog input[type=checkbox]')
    assert.equal(await page.locator('dialog button[type=submit]').isDisabled(), true, 'a picture that is not decoration needs words')
    await page.fill('dialog textarea', 'the logo of the club')
    await page.click('dialog button[type=submit]')
    await page.waitForFunction(() => document.querySelector('.obj.image')?.getAttribute('aria-label') === 'Picture: the logo of the club')

    await page.keyboard.press('Control+Alt+d')
    await page.waitForSelector('dialog[open] textarea')
    assert.equal(await page.inputValue('dialog textarea'), 'the logo of the club')
    await page.keyboard.press('Escape')

    // -- the keys typed in the dialog are the dialog's: not the arrows that move, nor Backspace that deletes, the text
    // box behind it (UX-78)
    await page.click('.menus .title:text-is("Edit")')
    await page.click('.menus .drop [role=menuitem]:has-text("Text Box")')
    const box = page.locator('.obj.text')
    await box.waitFor()
    await page.keyboard.press('Escape') // leave its text
    const slide = await page.locator('[data-testid=slide]').boundingBox()
    await page.mouse.click(slide.x + slide.width - 20, slide.y + slide.height - 20) // nothing is selected now
    const at = async () => JSON.stringify(await box.boundingBox())
    const placed = await at()
    await box.click({ button: 'right' })
    await page.getByRole('menuitem', { name: 'Name & describe…' }).click()
    const name = page.locator('dialog[open] input').first()
    await name.waitFor()
    const given = await name.inputValue()
    await name.focus()
    await page.keyboard.press('End')
    await page.keyboard.press('ArrowLeft')
    await page.keyboard.press('ArrowRight')
    await page.keyboard.press('ArrowDown')
    await page.waitForTimeout(400) // a move would have been seen by now
    assert.equal(await at(), placed, 'the arrow keys moved the text box behind the dialog')
    await page.keyboard.press('Backspace')
    await page.waitForTimeout(400) // so would a delete
    assert.equal(await box.count(), 1, 'Backspace deleted the text box behind the dialog')
    assert.equal(await name.inputValue(), given.slice(0, -1), 'Backspace should have edited the name')
    assert.equal(await page.locator('dialog[open]').count(), 1, 'the dialog should still be open')
    await name.fill('Title box')
    await page.click('dialog button[type=submit]')
    await page.waitForSelector('dialog[open]', { state: 'detached' })
    await page.waitForFunction(() => [...document.querySelectorAll('ol.log > li.entry')].some((e) => e.textContent.includes('Title box')), null, { timeout: 8000 }) // the history says who named it

    assert.deepEqual(errors, [])
    console.log('describe-creates: ok')
  } catch (e) {
    await page.screenshot({ path: '/tmp/describe-creates-fail.png' }).catch(() => undefined)
    console.error(e)
    process.exitCode = 1
  } finally {
    await browser.close()
  }
})()
