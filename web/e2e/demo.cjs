// Two people and the assistant in one table, in two real browser windows.
const { chromium } = require('playwright')
const assert = require('node:assert/strict')

const URL = process.env.URL ?? 'http://127.0.0.1:8765/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `demo-${Date.now() % 100000}`
const ANN = ['ann', 'Ann-has-a-Password-1']
const BEN = ['ben', 'Ben-has-a-Password-2']

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (...a) => console.log(...a)

async function open(browser, [user, password], create) {
  const context = await browser.newContext({ viewport: { width: 1360, height: 800 } })
  const page = await context.newPage()
  page.errors = []
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
  await page.waitForSelector('.viewport')
  await page.waitForFunction(() => document.querySelector('.health.open'))
  return page
}

async function cellAt(page, row, col) {
  const box = await page.locator('.viewport').boundingBox()
  return { x: box.x + 52 + col * 96 + 40, y: box.y + 26 + row * 26 + 13 }
}
async function click(page, row, col) {
  const p = await cellAt(page, row, col)
  await page.mouse.click(p.x, p.y)
}
// `.cell.blank` is the empty active cell the grid draws for screen readers (UX-02), not a cell with content
const cells = (page) => page.$$eval('.cell:not(.blank)', (els) => els.map((e) => e.textContent.trim()))
const history = (page) => page.$$eval('.entry', (els) => els.map((e) => e.textContent.replace(/\s+/g, ' ').trim()))
const chat = (page) => page.$$eval('.msg', (els) => els.map((e) => e.textContent.replace(/\s+/g, ' ').trim()))
async function waitFor(page, fn, arg, what) {
  try {
    await page.waitForFunction(fn, arg, { timeout: 8000 })
  } catch {
    throw new Error('timed out waiting for ' + what)
  }
}
// A menu item by its path: `menu(page, 'File', 'Manage', 'Share')` opens File, then Manage ▸, then clicks Share….
async function menu(page, title, ...path) {
  await page.click(`.menus .title:text-is("${title}")`)
  for (const item of path) await page.click(`.menus .drop [role=menuitem]:has-text("${item}")`)
}

;(async () => {
  const browser = await chromium.launch()
  try {
    // ---- ann makes a document and types a small table
    const ann = await open(browser, ANN, true)
    assert.equal(await ann.locator('.doc').textContent(), DOC)
    log('ann created', DOC)
    await click(ann, 0, 0)
    await ann.keyboard.type('Item')
    await ann.keyboard.press('Tab')
    await ann.keyboard.type('Amount')
    await ann.keyboard.press('Enter')
    await click(ann, 1, 0)
    await ann.keyboard.type('Rent')
    await ann.keyboard.press('Tab')
    await ann.keyboard.type('1200')
    await ann.keyboard.press('Enter')
    await ann.keyboard.type('450') // the selection moved down to B3 after Enter
    await ann.keyboard.press('Enter')
    await waitFor(ann, () => [...document.querySelectorAll('.cell:not(.blank)')].length >= 5, null, 'cells')
    assert.deepEqual((await cells(ann)).sort(), ['1200', '450', 'Amount', 'Item', 'Rent'].sort())
    const entries = await history(ann)
    assert.ok(entries.some((e) => e.includes('B2 = 1200')), 'history says B2 = 1200: ' + entries.join(' | '))
    log('ann typed', entries.length, 'history entries')
    await ann.screenshot({ path: `${SHOTS}/03-ann-typed.png` })

    // numbers are right-aligned, text left
    const aligns = await ann.$$eval('.cell:not(.blank)', (els) => els.map((e) => [e.textContent.trim(), e.className]))
    assert.ok(aligns.find(([t, c]) => t === '1200' && c.includes('right')))

    // status bar sums the selection
    await click(ann, 1, 1)
    await ann.keyboard.down('Shift')
    await click(ann, 2, 1)
    await ann.keyboard.up('Shift')
    await waitFor(ann, () => document.querySelector('.stats')?.textContent.includes('1650'), null, 'sum 1650')
    log('status bar:', (await ann.locator('.stats').textContent()).replace(/\s+/g, ' '))

    // ---- ann shares the document with ben
    await menu(ann, 'File', 'Manage', 'Share')
    await ann.fill('.modal input >> nth=0', BEN[0])
    await ann.fill('.modal input >> nth=1', BEN[1])
    await ann.click('.modal button:has-text("Add person")')
    await ann.waitForSelector('.added')
    await ann.keyboard.press('Escape')

    // ---- ben joins; he sees the table, the history and who is here
    const ben = await open(browser, BEN, false)
    await waitFor(ben, () => [...document.querySelectorAll('.cell:not(.blank)')].length >= 5, null, "ben's cells")
    assert.ok((await history(ben)).some((e) => e.includes('B2 = 1200')))
    const people = await ben.$$eval('.people li', (els) => els.map((e) => e.title))
    assert.ok(people.some((t) => t.startsWith('ann')) && people.some((t) => t === 'ai'), 'people: ' + people)
    await waitFor(ann, () => document.querySelectorAll('.people li').length === 3, null, 'ann sees three participants')
    log('ben joined; people:', people.join(', '))

    // ---- ben starts editing B2: ann sees the lock, and cannot edit that cell
    await click(ben, 1, 1)
    await ben.keyboard.press('F2')
    await waitFor(ann, () => document.querySelector('.outline.locked .tag')?.textContent.includes('ben'), null, 'ann sees ben editing')
    await ann.screenshot({ path: `${SHOTS}/04-ann-sees-ben-editing.png` })
    await click(ann, 1, 1)
    await ann.keyboard.press('F2')
    await waitFor(ann, () => document.querySelector('.toast')?.textContent.includes('ben'), null, 'toast about ben')
    log('ann is told:', await ann.locator('.toast').textContent())
    assert.equal(await ann.locator('.editor').count(), 0, 'the editor did not open')
    // ben types a new number
    await ben.keyboard.press('Control+a')
    await ben.keyboard.type('1300')
    await ben.keyboard.press('Enter')
    await waitFor(ann, () => [...document.querySelectorAll('.cell:not(.blank)')].some((e) => e.textContent.trim() === '1300'), null, 'ann sees 1300')
    await waitFor(ann, () => !document.querySelector('.outline.locked'), null, 'lock released')
    assert.ok((await history(ann)).some((e) => e.includes('ben') && e.includes('B2 = 1300')))
    log('ben changed B2 to 1300; ann sees it live')

    // ---- ann asks the assistant
    // The switch sits directly above the panel's tabs, and the half that is not chosen can be read on the dark panel
    // (it was ink on ink in the light theme, 2026-11-12): WCAG contrast of its text against the panel, at least 4.5.
    const switchCheck = await ann.evaluate(() => {
      const lum = (rgb) => {
        const [r, g, b] = rgb.match(/[\d.]+/g).slice(0, 3).map((v) => { const c = Number(v) / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 })
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
      }
      const mode = document.querySelector('[data-testid=ai-mode]')
      const off = mode.querySelector('[aria-checked=false]')
      const panel = getComputedStyle(document.querySelector('aside.panel')).backgroundColor
      const [a, b] = [lum(getComputedStyle(off).color), lum(panel)].sort((x, y) => y - x)
      return { aboveTabs: mode.nextElementSibling?.classList.contains('tabs'), contrast: (a + 0.05) / (b + 0.05) }
    })
    assert.ok(switchCheck.aboveTabs, 'the AI switch is directly above the tabs')
    assert.ok(switchCheck.contrast >= 4.5, `the unchosen half is readable: ${switchCheck.contrast.toFixed(2)}`)
    // A person starts with "Suggest first" (D262), and computes cannot propose yet (E7.8): ann lets it act.
    assert.equal(await ann.locator('[data-testid=ai-mode] [aria-checked=true]').getAttribute('data-mode'), 'suggest')
    await ann.click('[data-testid=ai-mode] [data-mode=act]')
    await waitFor(ann, () => document.querySelector('[data-testid=ai-mode] [aria-checked=true]')?.dataset.mode === 'act', null, 'act at once')
    await ann.fill('.write input', '@ai build an example budget')
    await ann.press('.write input', 'Enter')
    await waitFor(ann, () => document.querySelector('.typing'), null, 'ai is working')
    await sleep(1500)
    await ann.screenshot({ path: `${SHOTS}/05-ai-working.png` })
    const aiOutline = await ann.locator('.outline.ai').count()
    log('ai cursor visible while it works:', aiOutline > 0)
    await waitFor(ann, () => [...document.querySelectorAll('.msg.ai')].some((e) => e.textContent.includes('Done.')), null, 'ai done')
    await waitFor(ben, () => [...document.querySelectorAll('.cell:not(.blank)')].some((e) => e.textContent.trim() === 'Savings'), null, 'ben sees the budget')
    const aiEntries = (await history(ben)).filter((e) => e.startsWith('ai'))
    assert.ok(aiEntries.length >= 5, 'ai made entries: ' + aiEntries.length)
    assert.equal((await chat(ben)).filter((m) => m.startsWith('ai→')).length, 0, 'ben does not see the answer meant for ann')
    log('ai made', aiEntries.length, 'history entries; the answer went to ann only')
    await ann.screenshot({ path: `${SHOTS}/06-ai-done.png` })
    await ben.screenshot({ path: `${SHOTS}/07-ben-sees-ai.png` })

    // ---- ann asks for a sum; the number lands in her cell
    await ann.fill('.write input', '@ai sum B2:B5 into B7')
    await ann.press('.write input', 'Enter')
    await waitFor(ann, () => [...document.querySelectorAll('.msg.ai')].some((e) => e.textContent.includes('I wrote =SUM(B2:B5)')), null, 'ai sum')
    await click(ann, 6, 1)
    await waitFor(ann, () => document.querySelector('.text').value !== '', null, 'formula bar shows B7')
    const b7 = await ann.inputValue('.text')
    log('B7 =', b7)

    // ---- undo: ann can only undo her own work, and not past a colleague's later change
    await ann.click('.history button[aria-label=undo]')
    await sleep(500)
    const note = (await ann.locator('.toast').count()) ? await ann.locator('.toast').textContent() : ''
    log('ann undo ->', note || '(worked)')

    // ---- a checkpoint
    await ann.keyboard.press('Control+s')
    await waitFor(ann, () => document.querySelector('.mark'), null, 'checkpoint marker')
    log('checkpoint:', (await ann.locator('.mark').first().textContent()).trim())

    // ---- reload: everything is still there, including the chat
    await ann.reload()
    await ann.fill('input[name=document]', DOC)
    await ann.fill('input[name=user]', ANN[0])
    await ann.fill('input[name=password]', ANN[1])
    await ann.click('button:text-is("Open")')
    await ann.waitForSelector('.viewport')
    await waitFor(ann, () => [...document.querySelectorAll('.cell:not(.blank)')].some((e) => e.textContent.trim() === 'Savings'), null, 'cells after reload')
    assert.ok((await chat(ann)).some((m) => m.includes('example budget') || m.includes('Done.')), 'chat is back')
    log('after a reload the table, history and chat are back')

    // ---- a wrong password is refused
    const bad = await browser.newPage()
    await bad.goto(URL)
    await bad.fill('input[name=document]', DOC)
    await bad.fill('input[name=user]', 'ann')
    await bad.fill('input[name=password]', 'wrong wrong wrong')
    await bad.click('button:text-is("Open")')
    await bad.waitForSelector('.error')
    log('wrong password ->', await bad.locator('.error').textContent())

    for (const [name, page] of [['ann', ann], ['ben', ben]]) assert.deepEqual(page.errors, [], `${name} page errors`)
    log('\nALL GOOD')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error('FAILED:', e.message)
  process.exit(1)
})
