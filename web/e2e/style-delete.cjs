// Deleting and hiding a style from All styles…, in a real browser (E1.10, D226, D780, D785; server:
// --model claudia_composes:TextModel). Assign another style (the way that changes a look, said first), re-base (keeps
// every look, and the new style waits for its name), Undo, Hide and Show of a built-in style and the Alt access keys.
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8766/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `style-delete-${Date.now() % 100000}`
const log = (...a) => console.log(...a)

const look = (page, n) =>
  page.$$eval('[data-testid=text] [data-block]', (els, n) => {
    const c = getComputedStyle(els[n])
    return { cls: els[n].className, weight: c.fontWeight }
  }, n)

async function allStyles(page) {
  await page.click('text=Format')
  await page.click('text=All Styles…')
  await page.waitForSelector('[data-testid=styles-list]')
}

async function main() {
  const browser = await chromium.launch(process.env.CLAUDIA_CHROMIUM ? { executablePath: process.env.CLAUDIA_CHROMIUM } : {})
  const context = await browser.newContext({ viewport: { width: 1360, height: 860 } })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push('console: ' + m.text()))
  await page.goto(URL)
  await page.fill('input[name=document]', DOC)
  await page.fill('input[name=user]', 'ann')
  await page.fill('input[name=password]', 'Ann has a password 1')
  await page.click('text=Create document')
  await page.waitForSelector('[data-testid=recovery-key]')
  await page.check('.modal input[type=checkbox]')
  await page.click('.modal button:text-is("Continue")')
  await page.waitForSelector('[data-testid=text]')
  await page.waitForFunction(() => document.querySelector('.health.open'))

  await page.click('[data-testid=text]')
  await page.keyboard.type('A title. ')
  await page.keyboard.press('Enter')
  await page.keyboard.type('A paragraph that gets a style of its own. ')
  await page.keyboard.press('Enter')
  await page.keyboard.type('A paragraph of plain body text. ')
  await page.waitForTimeout(900)

  // a style of the document's own: bold, this paragraph only, and named
  const second = page.locator('[data-testid=text] [data-block]').nth(1)
  await second.click()
  await second.click({ button: 'right' })
  await page.waitForSelector('[data-testid=style-menu]')
  await page.click('[data-testid=bold]')
  await page.waitForFunction(() => document.querySelectorAll('[data-testid=text] [data-block]')[1].className.includes('changed'))
  await page.fill('[data-testid=name-invitation] input', 'Pull note')
  await page.click('[data-testid=name-invitation] button[type=submit]')
  await page.waitForSelector('[data-testid=name-invitation]', { state: 'detached' })
  await page.keyboard.press('Escape')
  assert.equal((await look(page, 1)).weight, '700')
  const own = (await look(page, 1)).cls.match(/st-([\w-]+)/)[1]
  log('a style of the document’s own:', own)

  // All styles: the document's own style can be deleted, a built-in one can only be hidden
  await allStyles(page)
  const row = (id) => page.locator(`[data-testid=styles-list] [data-style=${id}]`)
  assert.equal(await row(own).locator('[data-delete]').count(), 1)
  assert.equal(await row(own).locator('[data-hide]').count(), 0)
  assert.equal(await row('body').locator('[data-delete]').count(), 0, 'a built-in style cannot be deleted')
  assert.equal(await row('body').locator('[data-hide]').count(), 1)
  await page.screenshot({ path: `${SHOTS}/style-delete-0-list.png` })

  // Delete… with the access key: Alt+D on the row the focus is on
  await row(own).locator('[data-edit]').focus()
  await page.keyboard.press('Alt+d')
  await page.waitForSelector('[data-testid=style-delete]')
  assert.equal(await page.locator('[data-testid=way-assign]').isChecked(), true, 'assigning is the first way and preselected')
  assert.equal(await page.locator('[data-testid=assign-target]').inputValue(), 'body', 'with the plain style of the kind chosen')
  assert.match(await page.locator('[data-testid=looks-change]').innerText(), /Will look different: 1 paragraph/)
  assert.equal(await page.locator('[data-testid=delete-style]').isEnabled(), true)
  await page.screenshot({ path: `${SHOTS}/style-delete-1-assign.png` })

  // re-basing wants a style, and offers only those that keep the look
  await page.check('[data-testid=way-rebase]')
  assert.equal(await page.locator('[data-testid=delete-style]').isDisabled(), true, 're-basing waits for a style to re-base on')
  await page.screenshot({ path: `${SHOTS}/style-delete-2-rebase.png` })
  await page.check('[data-testid=way-assign]')

  // assign Body text: the paragraph looks like it, one announcement, Undo puts it back
  await page.click('[data-testid=delete-style]')
  await page.waitForSelector('[data-testid=style-delete]', { state: 'detached' })
  await page.waitForFunction(() => document.querySelectorAll('[data-testid=text] [data-block]')[1].className.includes('st-body'))
  assert.equal((await look(page, 1)).weight, '400', 'assigning Body text changes the look, as said')
  assert.match(await page.locator('[data-testid=deleted]').innerText(), /deleted\. What had it now has “Body text”/)
  assert.equal(await row(own).count(), 0)
  await page.screenshot({ path: `${SHOTS}/style-delete-3-assigned.png` })
  await page.click('[data-testid=undo-delete]')
  await page.waitForFunction((id) => document.querySelectorAll('[data-testid=text] [data-block]')[1].className.includes(`st-${id}`), own)
  assert.equal((await look(page, 1)).weight, '700')
  await page.waitForSelector(`[data-testid=styles-list] [data-style=${own}]`)
  log('assigning Body text changed the look and Undo brought everything back')

  // re-base on Body text: the look is kept, through a new style that waits for its name
  await row(own).locator('[data-delete]').click()
  await page.waitForSelector('[data-testid=style-delete]')
  await page.check('[data-testid=way-rebase]')
  await page.selectOption('[data-testid=rebase-target]', 'body')
  assert.equal(await page.locator('[data-testid=looks-change]').count(), 0, 're-basing says nothing will look different')
  await page.click('[data-testid=delete-style]')
  await page.waitForSelector('[data-testid=deleted]')
  assert.match(await page.locator('[data-testid=deleted]').innerText(), /Pull note \(kept\)/)
  assert.equal((await look(page, 1)).weight, '700', 're-basing keeps the look')
  await page.screenshot({ path: `${SHOTS}/style-delete-4-rebased.png` })
  await page.click('[data-testid=name-it]')
  await page.fill('.rename input', 'Pull note, again')
  await page.click('.rename button[type=submit]')
  await page.waitForFunction(() => [...document.querySelectorAll('[data-testid=styles-list] .sample')].some((e) => e.textContent === 'Pull note, again'))
  log('re-basing kept the look; the new style waited for a name and got one')

  // hiding a built-in style: gone from the list and the menus, back with "Show hidden styles"
  await row('body').locator('[data-hide]').focus()
  await page.keyboard.press('Alt+h')
  await page.waitForSelector('[data-testid=styles-list] [data-style=body]', { state: 'detached' })
  await page.check('[data-testid=show-hidden]')
  await page.waitForSelector('[data-testid=styles-list] [data-style=body]')
  assert.match(await row('body').innerText(), /hidden/)
  await page.screenshot({ path: `${SHOTS}/style-delete-5-hidden.png` })
  await row('body').locator('[data-hide]').click() // Show
  await page.uncheck('[data-testid=show-hidden]').catch(() => undefined) // the checkbox goes when nothing is hidden
  await page.waitForSelector('[data-testid=show-hidden]', { state: 'detached' })
  await page.waitForSelector('[data-testid=styles-list] [data-style=body]')
  log('hiding and showing a built-in style')

  assert.deepEqual(errors, [])
  await browser.close()
  log('OK')
}
main().catch((e) => {
  console.error(e)
  process.exit(1)
})
