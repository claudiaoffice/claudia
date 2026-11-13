// The macOS client's window, in a real browser: the built shell page (clients/macos/apps/<app>), the built core as a real
// process, a real Claudia server and the real web app in the frame. Only Neutralino is faked -- its client library
// object (menu recorded, events, `extensions.dispatch` over a WebSocket to the core, broadcasts back) -- because that is
// the one piece that needs a Mac. What this shows, per app: the shell page and the web app complete the handshake; the
// web app's own menu bar gives way to the native one; a click in the native menu does what it says in the document;
// the window's end stops the server it started. And once more with a server given on the command line (`--server`).
//
//   (cd clients/macos && npm ci && npm run build) && cd web && npm run build && npm run e2e:macos-shell
//
// Needs: the built macOS client (clients/macos/apps/<app>/{index.html,shell/,ext/core.mjs}), the built web app
// (web/.output/public), the Python environment (.venv). Not covered, and for a Mac: Neutralino itself, WKWebView, the
// real menu.
const { chromium } = require('playwright')
const { createRequire } = require('node:module')
const { spawn } = require('node:child_process')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const http = require('node:http')
const os = require('node:os')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '../..')
const MACOS = path.join(ROOT, 'clients/macos')
const SHOTS = process.env.SHOTS
const APPS = (process.env.APPS || 'computes,composes,creates').split(',')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function need(file, how) {
  if (!fs.existsSync(file)) throw new Error(`${path.relative(ROOT, file)} is missing: ${how}`)
}
need(path.join(MACOS, 'node_modules/ws'), 'run `npm ci` in clients/macos')
const { WebSocketServer } = createRequire(path.join(MACOS, 'package.json'))('ws')

// The client library as the shell page sees it. `window.__dispatch` and the broadcast hook are set up by the test.
const FAKE_NEUTRALINO = `
window.__menus = []; window.__handlers = {}
window.Neutralino = {
  init() {},
  app: { exit: async () => {} },
  window: { setMainMenu: async (items) => { window.__menus.push(items) } },
  events: { on: async (name, handler) => { window.__handlers[name] = handler } },
  extensions: { dispatch: async (id, event, data) => window.__dispatch(event, data), getStats: async () => ({ loaded: [id], connected: [id] }) },
}
`

/** Neutralino's static file server for one app folder, with the fake client library in place of the real one. */
function servePages(appDir) {
  const server = http.createServer((req, res) => {
    const name = new URL(req.url, 'http://x').pathname
    try {
      const body = name === '/js/neutralino.js' ? FAKE_NEUTRALINO : fs.readFileSync(path.join(appDir, name === '/' ? 'index.html' : name))
      res.writeHead(200, { 'content-type': name.endsWith('.js') ? 'text/javascript' : 'text/html' }).end(body)
    } catch {
      res.writeHead(404).end()
    }
  })
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)))
}

/** A window of one app: the core as a process, linked to this test as if the test were Neutralino. */
async function openWindow(browser, app, server) {
  const appDir = path.join(MACOS, 'apps', app)
  need(path.join(appDir, 'ext/core.mjs'), 'run `npm run build` in clients/macos')
  need(path.join(appDir, 'index.html'), 'run `npm run build` in clients/macos')
  need(path.join(ROOT, 'web/.output/public/index.html'), 'run `npm run build` in web')
  const home = fs.mkdtempSync(path.join(os.tmpdir(), `claudia-e2e-macos-${app}-`))

  const neutralino = new WebSocketServer({ host: '127.0.0.1', port: 0 })
  await new Promise((resolve) => neutralino.once('listening', resolve))
  let coreSocket = null
  const fromCore = []
  const handlers = { onMessage: () => {} }
  neutralino.on('connection', (socket) => {
    coreSocket = socket
    socket.on('message', (raw) => {
      const data = JSON.parse(String(raw)).data
      fromCore.push(data)
      handlers.onMessage(data)
    })
  })
  const args = [path.join(appDir, 'ext/core.mjs'), `--app=${app}`, ...(server ? [`--server=${server}`] : [])]
  const core = spawn(process.execPath, args, { env: { PATH: process.env.PATH, HOME: home }, stdio: ['pipe', 'inherit', 'inherit'] })
  const exited = new Promise((resolve) => core.once('exit', resolve))
  core.stdin.write(JSON.stringify({ nlPort: neutralino.address().port, nlToken: 'token', nlConnectToken: 'connect', nlExtensionId: 'de.claudiaoffice.core' }))

  const pages = await servePages(appDir)
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 860 } })).newPage()
  page.consoleLines = []
  page.on('console', (message) => page.consoleLines.push(message.text()))
  page.on('pageerror', (error) => page.consoleLines.push(`[pageerror] ${error.message}`))
  await page.exposeFunction('__dispatch', (event, data) => coreSocket.send(JSON.stringify({ event, data })))
  handlers.onMessage = (data) => page.evaluate(({ event, data: detail }) => window.__handlers[event]?.({ detail }), data).catch(() => {})
  await page.goto(`http://127.0.0.1:${pages.address().port}/`)

  return {
    page,
    fromCore,
    /** The page of the web app inside the shell's frame, once it is there. */
    async frame() {
      const deadline = Date.now() + 40000
      while (Date.now() < deadline) {
        const frame = page.frames().find((f) => f !== page.mainFrame() && f.url().startsWith('http'))
        if (frame) return frame
        const status = await page.evaluate(() => ({ hidden: document.getElementById('status').hidden, title: document.getElementById('status-title').textContent, details: document.getElementById('status-details').textContent }))
        if (!status.hidden && status.title.startsWith('Claudia could not')) throw new Error(`the window says: ${status.title} ${status.details}`)
        await sleep(200)
      }
      throw new Error('the window never showed a page; it says: ' + (await page.locator('#status').innerText()))
    },
    menuSets: () => page.evaluate(() => window.__menus.length),
    menuJson: () => page.evaluate(() => JSON.stringify(window.__menus[0])),
    /** What a click on a native menu item sends to the page (Neutralino's `mainMenuItemClicked`). */
    click: (id, text) => page.evaluate(({ id, text }) => window.__handlers.mainMenuItemClicked({ detail: { id, text } }), { id, text }),
    async close() {
      for (const socket of neutralino.clients) socket.close() // the window's end: the core must stop what it started
      const code = await Promise.race([exited, sleep(10000).then(() => 'timeout')])
      if (code === 'timeout') core.kill('SIGKILL')
      neutralino.close()
      pages.close()
      return code
    },
  }
}

async function ready(url) {
  for (let i = 0; i < 100; i++) {
    try {
      if ((await fetch(url + 'api/health')).ok) return
    } catch {
      // not up yet
    }
    await sleep(200)
  }
  throw new Error('the server did not start: ' + url)
}
const down = async (url) => fetch(url + 'api/health', { signal: AbortSignal.timeout(2000) }).then(() => false, () => true)

/** Makes a document the way a person does, and lands inside it. */
const WORKSPACE = { computes: '.viewport', composes: '[data-testid=text]', creates: '[data-testid=slide]' }
async function createDocument(frame, app, name) {
  await frame.fill('input[name=document]', name)
  await frame.fill('input[name=user]', 'tester')
  await frame.fill('input[name=password]', 'Secret-pass-1234')
  await frame.click('text=Create document')
  await frame.waitForSelector('[data-testid=recovery-key]')
  await frame.check('.modal input[type=checkbox]')
  await frame.click('.modal button:text-is("Continue")')
  await frame.waitForSelector(WORKSPACE[app])
  await frame.waitForSelector('.health.open')
}

const menuBarGone = (frame) => frame.evaluate(() => { const nav = document.querySelector('nav.menus'); return nav !== null && nav.getBoundingClientRect().height === 0 })

async function shot(page, name) {
  if (SHOTS) {
    fs.mkdirSync(SHOTS, { recursive: true })
    await page.screenshot({ path: path.join(SHOTS, `macos-shell-${name}.png`) })
  }
}

/** The checks that every window must pass, whatever app and whichever server it shows. */
async function checkWindow(window, app, label) {
  const frame = await window.frame()
  const origin = new URL(frame.url()).origin
  await window.page.waitForFunction(() => document.getElementById('status').hidden, null, { timeout: 15000 }).catch(() => {
    throw new Error(`${label}: the status screen never gave way to the app`)
  })

  // the shell's servers reach the web app's welcome page (contract capability `servers`)
  await frame.waitForSelector('input[name=document]')
  assert.ok((await frame.evaluate(() => document.body.innerText)).includes(new URL(origin).host), `${label}: the welcome page lists this server`)

  await createDocument(frame, app, `e2e-${app}`)
  await frame.waitForFunction(() => document.querySelector('nav.menus')?.classList.contains('hidden'), null, { timeout: 15000 }).catch(() => {
    throw new Error(`${label}: the web app kept its own menu bar; the console says:\n${window.page.consoleLines.join('\n')}`)
  })
  assert.ok(await menuBarGone(frame), `${label}: the web menu bar takes no room`)
  assert.ok((await window.menuSets()) >= 1, `${label}: a native menu was set`)
  assert.ok((await window.menuJson()).includes('Save New Checkpoint'), `${label}: the native menu has the app's items`)

  // a click in the native menu does what its label says, in the document
  await window.click('file.save-as', 'Save New Checkpoint…')
  await frame.waitForSelector('.modal:has-text("Save new checkpoint")', { timeout: 10000 }).catch(() => {
    throw new Error(`${label}: "Save New Checkpoint…" in the native menu did nothing; the console says:\n${window.page.consoleLines.join('\n')}`)
  })
  await window.page.keyboard.press('Escape')
  await shot(window.page, `${label.replace(/\W+/g, '-')}`)
  const unexpected = window.page.consoleLines.filter((line) => /\[pageerror\]|could not start|has not said hello|was not sent/i.test(line))
  assert.deepEqual(unexpected, [], `${label}: nothing went wrong in the shell page's console`)
  return origin
}

;(async () => {
  // CHROMIUM: a browser binary to use instead of Playwright's own (for a machine with another Playwright version).
  const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {})
  let failed = null
  try {
    // ---- each app, with the server the window starts itself
    for (const app of APPS) {
      const window = await openWindow(browser, app, null)
      try {
        const origin = await checkWindow(window, app, `${app}, its own server`)
        assert.match(origin, /^http:\/\/127\.0\.0\.1:\d+$/, 'its own server is on this computer, plain http')
        const code = await window.close()
        assert.equal(code, 0, `${app}: the core ended cleanly with the window`)
        assert.ok(await down(origin + '/'), `${app}: the server the window started is stopped with it`)
        console.log(`${app}: handshake, native menu, checkpoint dialog, server stopped with the window`)
      } catch (problem) {
        await shot(window.page, `${app}-failed`)
        await window.close().catch(() => {})
        throw problem
      }
    }

    // ---- a server given with --server (here one on this computer: plain http is allowed only there)
    const port = 8791
    const url = `http://127.0.0.1:${port}/`
    const data = fs.mkdtempSync(path.join(os.tmpdir(), 'claudia-e2e-macos-server-'))
    const server = spawn(
      path.join(ROOT, '.venv/bin/python'),
      ['-m', 'claudia_server', '--no-tls', '--port', String(port), '--dir', data, '--web', path.join(ROOT, 'web/.output/public'), '--model', 'claudia_computes:WorkbookModel'],
      { cwd: ROOT, stdio: 'ignore' },
    )
    try {
      await ready(url)
      const window = await openWindow(browser, 'computes', url.slice(0, -1))
      try {
        const origin = await checkWindow(window, 'computes', 'computes, --server')
        assert.equal(origin, url.slice(0, -1), 'the window shows the server it was given')
        assert.ok(window.fromCore.some((m) => m.data.kind === 'status' && /Connecting to 127\.0\.0\.1/.test(m.data.title)), 'it said it was connecting')
        const code = await window.close()
        assert.equal(code, 0, 'the core ended cleanly')
        assert.equal(await down(url), false, 'a server the window was only given is not stopped with it')
        console.log('computes --server: given server shown, and left running when the window ends')
      } catch (problem) {
        await shot(window.page, 'server-failed')
        await window.close().catch(() => {})
        throw problem
      }
    } finally {
      server.kill('SIGTERM')
      await new Promise((resolve) => server.once('exit', resolve))
    }
  } catch (problem) {
    failed = problem
  }
  await browser.close()
  if (failed) {
    console.error(failed.stack || failed)
    process.exit(1)
  }
  console.log('macOS shell window: ok')
  process.exit(0)
})()
