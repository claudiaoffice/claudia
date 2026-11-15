// Paragraphs as things in a real browser (D554): in a text, ann writes a heading and a paragraph, types "#" in the chat
// and picks the heading, which has no name yet: it is named by its words and the tag says so. Edit ▸ Reference in Chat
// puts a tag for the paragraph with the caret in the box. ben clicks the heading's tag and the text outlines it.
// Start a text server first (as CI does): python -m claudia_server --model claudia_composes:TextModel ...
// Run: URL=http://127.0.0.1:8766/ npm run e2e:dock-text
const { chromium } = require('playwright')
const assert = require('node:assert/strict')
const fs = require('node:fs')

const URL = process.env.URL ?? 'http://127.0.0.1:8766/'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const DOC = `paragraphs-${Date.now() % 100000}`
const ANN = ['ann', 'Ann has a password 1']
const BEN = ['ben', 'Ben has a password 1']
const log = (...a) => console.log(...a)
const chatBox = '.write [role=combobox]'

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
  await page.waitForSelector('[data-testid=text]')
  await page.waitForFunction(() => document.querySelector('.health.open'))
  return page
}
async function menu(page, title, ...path) {
  await page.click(`.menus .title:text-is("${title}")`)
  for (const item of path) await page.click(`.menus .drop [role=menuitem]:has-text("${item}")`)
}

;(async () => {
  fs.mkdirSync(SHOTS, { recursive: true })
  const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {})
  try {
    const ann = await open(browser, ANN, true)
    await ann.click('[data-testid=text]')
    await ann.keyboard.type('Introduction')
    await ann.keyboard.press('Enter')
    await ann.keyboard.type('The quick brown fox jumps over the lazy dog.')
    await ann.click('[data-testid=text] [data-block]:first-child')
    await ann.click('[data-testid=style-button]')
    await ann.click('[data-style=heading-1]')
    await ann.waitForTimeout(600)
    log('ann wrote a heading and a paragraph')

    // ---- "#" offers the heading, which is named by its words when it is picked
    await ann.click(chatBox)
    await ann.keyboard.type('See #Intro')
    await ann.waitForSelector('#tag-list [role=option]:has-text("Introduction")')
    await ann.keyboard.press('Enter')
    await ann.waitForFunction((sel) => document.querySelector(sel)?.querySelector('.chip'), chatBox)
    await ann.keyboard.press('Enter')
    await ann.waitForSelector('.msg button.tag:text-is("#Introduction")')
    log('ann tagged the heading; it is called “Introduction”')

    // ---- Edit ▸ Reference in Chat: the paragraph with the caret
    await ann.click('[data-testid=text] [data-block]:nth-child(2)')
    await menu(ann, 'Edit', 'Reference in Chat')
    await ann.waitForFunction((sel) => document.querySelector(sel)?.querySelector('.chip')?.textContent.includes('Paragraph'), chatBox)
    log('Edit ▸ Reference in Chat put a tag for the paragraph in the box')

    // ---- ben follows the heading's tag
    await menu(ann, 'File', 'Manage', 'Share')
    await ann.fill('.modal input >> nth=0', BEN[0])
    await ann.fill('.modal input >> nth=1', BEN[1])
    await ann.click('.modal button:has-text("Add person")')
    await ann.waitForSelector('.added')
    await ann.keyboard.press('Escape')
    const ben = await open(browser, BEN, false)
    await ben.click('.msg button.tag:text-is("#Introduction")')
    await ben.waitForSelector('[data-testid=text] [data-block].pointed')
    const pointed = await ben.$eval('[data-testid=text] [data-block].pointed', (e) => e.textContent.trim())
    assert.equal(pointed, 'Introduction')
    log('ben clicked the tag and the heading is outlined')
    await ben.screenshot({ path: `${SHOTS}/dock-text.png` })

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
