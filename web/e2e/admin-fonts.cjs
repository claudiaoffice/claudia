// Server settings ▸ Fonts (E3.13 f, D1041): the page lists the catalogue, Add fonts… checks first and then adds, a
// collection added here can be renamed and removed. FONTS is a folder of font files to add (one of them forbidding
// embedding), as `uv run python scripts/make_admin_fonts_sample.py DIR` makes them.
// Run: URL=http://127.0.0.1:8766/ FONTS=/tmp/house-fonts npm run e2e:admin-fonts
const { chromium } = require('playwright')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const URL = process.env.URL ?? 'http://127.0.0.1:8766/'
const FONTS = process.env.FONTS ?? '/tmp/house-fonts'
const SHOTS = process.env.SHOTS ?? '/tmp/shots'
const ADMIN = ['anna', 'Anna has a password 1']
const log = (...a) => console.log(...a)

async function main() {
  fs.mkdirSync(SHOTS, { recursive: true })
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM }) // CHROMIUM: a browser of your own, if Playwright's is not installed
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } })
  const errors = []
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => m.type() === 'error' && !/40[19]/.test(m.text()) && errors.push('console: ' + m.text()))
  await page.goto(new globalThis.URL('admin/', URL).href)

  // the first administrator, or sign in
  if (await page.locator('text=Create administrator').count()) {
    await page.fill('input[autocomplete=username]', ADMIN[0])
    for (const field of await page.locator('input[type=password]').all()) await field.fill(ADMIN[1])
    await page.click('text=Create administrator') // the settings follow without a reload (CODE-48)
  } else {
    await page.fill('input[autocomplete=username]', ADMIN[0])
    await page.fill('input[type=password]', ADMIN[1])
    await page.click('button:text-is("Sign in")')
  }
  await page.click('nav >> text=Fonts').catch(async (e) => {
    await page.screenshot({ path: `${SHOTS}/admin-fonts-failed.png` })
    throw e
  })
  await page.waitForSelector('h1:text-is("Fonts")')
  const cards = await page.locator('.cards h3').allTextContents()
  assert.equal(cards[0], 'Shipped with Claudia')
  assert.ok(await page.locator('tbody th:text-is("Arimo")').count(), 'the shipped families are listed')
  assert.match(await page.locator('tr:has(th:text-is("Arimo"))').innerText(), /Arial/)
  await page.waitForTimeout(800) // the previews in their own faces
  await page.screenshot({ path: `${SHOTS}/admin-fonts-1-page.png`, fullPage: true })
  log('page ok:', cards.join(' | '))

  // Add fonts…: choose, check (nothing changes yet), add
  await page.click('text=Add fonts…')
  const files = fs.readdirSync(FONTS).filter((f) => /\.(ttf|otf|zip)$/i.test(f)).map((f) => path.join(FONTS, f))
  // too many at once is said before anything is sent; files given up are let go of on the server (CODE-49)
  const sent = []
  page.on('request', (r) => r.url().includes('/api/admin/fonts/files') && sent.push(r.method()))
  const one = { name: 'x.ttf', mimeType: 'font/ttf', buffer: fs.readFileSync(files[0]) }
  await page.setInputFiles('.modal input[type=file]', Array.from({ length: 65 }, (_, i) => ({ ...one, name: `x${i}.ttf` })))
  await page.waitForSelector('.modal [role=alert]:has-text("At most 64 files")')
  assert.deepEqual(sent, [])
  await page.setInputFiles('.modal input[type=file]', files)
  await page.waitForSelector(`text=${files.length} files chosen`)
  await Promise.all([page.waitForRequest((r) => r.method() === 'DELETE' && r.url().endsWith('/api/admin/fonts/files')), page.click('text=Start again')])
  assert.equal(await page.locator('text=files chosen').count(), 0)
  await page.setInputFiles('.modal input[type=file]', files)
  await page.waitForSelector(`text=${files.length} files chosen`)
  await page.fill('.modal .field:has-text("Name of the collection") input', 'City house fonts')
  await page.check('.modal input[value=this-server]')
  await page.fill('.modal .field:has-text("Licence") input', 'Licensed to the City for internal use (contract 2024-117)')
  await page.screenshot({ path: `${SHOTS}/admin-fonts-2-add-a.png` })
  await page.click('button:text-is("Check files")')
  await page.waitForSelector('.checks')
  assert.equal(await page.locator('.verdict:text-is("Left out")').count(), 1)
  assert.ok(await page.locator('.scope').innerText().then((s) => s.includes('Only people using this server receive them.')))
  await page.screenshot({ path: `${SHOTS}/admin-fonts-3-add-b.png` })
  await page.click('.modal button:has-text("Add 3 fonts")')
  await page.waitForSelector('.cards h3:text-is("City house fonts")')
  assert.match(await page.locator('[role=status]').innerText(), /Fonts added/)
  assert.ok(await page.locator('tbody th:text-is("Hausschrift Sans")').count())
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${SHOTS}/admin-fonts-4-added.png`, fullPage: true })
  log('added ok')

  // rename, then remove (danger-zone confirmation)
  const card = page.locator('.card:has(h3:text-is("City house fonts"))')
  await card.locator('button.more').click()
  await page.click('role=menuitem[name="Rename…"]')
  await page.fill('.modal input', 'City fonts')
  await page.click('.modal button:text-is("Rename")')
  await page.waitForSelector('.cards h3:text-is("City fonts")')
  await page.locator('.card:has(h3:text-is("City fonts")) button.more').click()
  await page.click('role=menuitem[name="Remove collection…"]')
  assert.match(await page.locator('.modal .warning').innerText(), /Hausschrift Sans/)
  await page.screenshot({ path: `${SHOTS}/admin-fonts-5-remove.png` })
  await page.click('.modal button:text-is("Remove collection")')
  await page.waitForSelector('text=Collection removed.')
  assert.equal(await page.locator('.cards h3:text-is("City fonts")').count(), 0)
  log('rename and remove ok')

  assert.deepEqual(errors, [])
  await browser.close()
  log('admin fonts: all ok')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
