// The shell page's logic with a fake Neutralino, a fake frame and a fake core: the menu, the frame messages (origin
// and source checked), the core's messages, and the order in which things start.
import { describe, expect, it } from 'vitest'
import { buildMainMenu, type ManifestListing } from '../src/menu.js'
import { ShellPage, knownActions, type PageEnv } from '../src/shell-page.js'
import { CORE_ID, FROM_CORE, TO_CORE } from '../src/core-protocol.js'
import listing from '../src/generated/menu.creates.json' with { type: 'json' }

const MENU = buildMainMenu(listing as ManifestListing, 'Claudia Creates')
const tick = () => new Promise((resolve) => setTimeout(resolve, 0))

function setup(overrides: { dispatchFails?: number; setMenuFails?: boolean; stats?: unknown } = {}) {
  const timers: Array<() => void> = []
  const listeners: Record<string, (event: { detail: unknown }) => void> = {}
  const dispatched: Array<{ id: string; event: string; data: any }> = []
  const menus: unknown[][] = []
  const calls: string[] = []
  let failures = overrides.dispatchFails ?? 0
  const neutralino = {
    init: () => calls.push('init'),
    app: { exit: async () => void calls.push('exit') },
    window: {
      setMainMenu: async (items: unknown[]) => {
        if (overrides.setMenuFails) throw new Error('no menu')
        calls.push('menu')
        menus.push(items)
      },
    },
    events: { on: async (name: string, handler: (event: { detail: unknown }) => void) => void (listeners[name] = handler) },
    extensions: {
      dispatch: async (id: string, event: string, data: unknown) => {
        if (failures-- > 0) throw new Error('NE_EX_EXTNOTC')
        dispatched.push({ id, event, data })
      },
      getStats: async () => overrides.stats ?? { loaded: ['de.claudiaoffice.core'], connected: [] },
    },
  }
  const posted: Array<{ data: string; origin: string }> = []
  const contentWindow = { postMessage: (data: string, origin: string) => posted.push({ data, origin }) }
  const frameListeners: Array<() => void> = []
  const frame = {
    src: '',
    contentWindow: contentWindow as typeof contentWindow | null,
    addEventListener: (_type: 'load', listener: () => void) => frameListeners.push(listener),
  }
  const statuses: Array<{ title: string; details?: string; error: boolean } | 'hidden'> = []
  const status = {
    show: (title: string, details: string | undefined, error: boolean) => statuses.push({ title, ...(details !== undefined ? { details } : {}), error }),
    hide: () => statuses.push('hidden'),
  }
  let windowListener: (event: { source: unknown; origin: string; data: unknown }) => void = () => {}
  const logged: string[] = []
  const env: PageEnv = {
    app: 'creates',
    version: '0.1.0',
    menu: MENU,
    neutralino: neutralino as never,
    frame: frame as never,
    status,
    onWindowMessage: (listener) => (windowListener = listener),
    sleep: async () => {},
    after: (_ms, action) => void timers.push(action),
    log: (m) => logged.push(m),
  }
  const page = new ShellPage(env)
  const core = (message: unknown) => listeners[FROM_CORE]!({ detail: message })
  const fromFrame = (message: unknown, origin = 'https://demo.example.org', source: unknown = contentWindow) =>
    windowListener({ source, origin, data: typeof message === 'string' ? message : JSON.stringify(message) })
  const fromFrameRaw = (data: unknown) => windowListener({ source: contentWindow, origin: 'https://demo.example.org', data })
  const menuClick = (id: string) => listeners.mainMenuItemClicked!({ detail: { id, text: id } })
  const toFrame = () => posted.map((p) => JSON.parse(p.data))
  const hello = (app = 'creates') => fromFrame({ type: 'hello', contract: 1, app })
  /** A page that is open and has said hello. */
  const open = async (origin = 'https://demo.example.org') => {
    await page.start()
    core({ kind: 'show', origin })
    hello()
    posted.length = 0
    dispatched.length = 0
  }
  /** The next second of the watch over the core. */
  const second = async () => {
    timers.shift()!()
    await tick()
  }
  return { second, timers, fromFrameRaw, page, listeners, dispatched, menus, calls, frame, frameListeners, statuses, posted, logged, core, fromFrame, menuClick, toFrame, hello, open, contentWindow }
}

describe('start', () => {
  it('starts Neutralino first, then listens, sets the native menu and asks the core to start', async () => {
    const t = setup()
    await t.page.start()
    expect(t.calls.slice(0, 2)).toEqual(['init', 'menu'])
    expect(Object.keys(t.listeners).sort()).toEqual([FROM_CORE, 'mainMenuItemClicked'].sort())
    expect(t.menus[0]).toEqual(MENU)
    expect(t.dispatched).toEqual([{ id: CORE_ID, event: TO_CORE, data: { kind: 'start' } }])
    expect(t.statuses[0]).toEqual({ title: 'Starting…', error: false })
  })

  it('asks again while the core is not connected yet (Neutralino refuses until it is)', async () => {
    const t = setup({ dispatchFails: 3 })
    await t.page.start()
    expect(t.dispatched).toHaveLength(1)
    expect(t.logged.filter((m) => m.includes('not there yet'))).toHaveLength(3)
  })

  it('says so, in the window, when the core never answers', async () => {
    const t = setup({ dispatchFails: 1000 })
    await t.page.start()
    expect(t.statuses.at(-1)).toMatchObject({ title: 'Claudia could not start', error: true })
  })

  it('asks again every second until the core has said anything, and then stops asking', async () => {
    const t = setup()
    await t.page.start()
    await t.second()
    await t.second()
    expect(t.dispatched.map((d) => d.data.kind)).toEqual(['start', 'start', 'start'])
    t.core({ kind: 'status', title: 'Starting Claudia Creates…', error: false })
    await t.second()
    expect(t.dispatched).toHaveLength(3)
    expect(t.timers).toHaveLength(0)
  })

  it('logs which extensions Neutralino has started while it waits (the log says whether the core is there at all)', async () => {
    const t = setup({ stats: { loaded: ['de.claudiaoffice.core'], connected: [] } })
    await t.page.start()
    await t.second()
    expect(t.logged.join('\n')).toContain('extensions: {"loaded":["de.claudiaoffice.core"],"connected":[]}')
  })

  it('tells where to look after twenty seconds without an answer, instead of staying on "Starting…"', async () => {
    const t = setup()
    await t.page.start()
    for (let second = 0; second < 20; second++) await t.second()
    expect(t.statuses.at(-1)).toMatchObject({ title: 'Claudia could not start', error: true })
    const details = (t.statuses.at(-1) as { details: string }).details
    expect(details).toContain('shell.log')
    expect(details).toContain('Inspect')
    expect(details).toContain('creates')
    expect(t.timers).toHaveLength(0) // it does not go on for ever
  })

  it('shows what the core says even after that, and not the timeout, when it is merely slow', async () => {
    const t = setup()
    await t.page.start()
    for (let second = 0; second < 20; second++) await t.second()
    t.core({ kind: 'status', title: 'Connecting to demo.example.org…', error: false })
    expect(t.statuses.at(-1)).toMatchObject({ title: 'Connecting to demo.example.org…', error: false })
  })

  it('goes on without a native menu that could not be set, and says so in the log', async () => {
    const t = setup({ setMenuFails: true })
    await t.page.start()
    expect(t.dispatched).toHaveLength(1)
    expect(t.logged.join('')).toContain('native menu could not be set')
  })
})

describe('a page that does not speak the contract', () => {
  it('is named in the log after five seconds, once, when it never says hello', async () => {
    const t = setup()
    await t.page.start()
    t.core({ kind: 'show', origin: 'https://demo.example.org' })
    t.frameListeners.forEach((l) => l())
    t.timers.pop()!() // the last timer is the watch over the hello
    expect(t.logged.join('\n')).toContain('has not said hello')
    expect(t.logged.join('\n')).toContain('55a9742')
  })

  it('says nothing when the page did say hello', async () => {
    const t = setup()
    await t.page.start()
    t.core({ kind: 'show', origin: 'https://demo.example.org' })
    t.frameListeners.forEach((l) => l())
    t.hello()
    t.timers.pop()!()
    expect(t.logged.join('\n')).not.toContain('has not said hello')
  })

  it('logs a menu click that nobody could act on, instead of dropping it without a trace', async () => {
    const t = setup()
    await t.page.start()
    t.core({ kind: 'show', origin: 'https://demo.example.org' })
    t.menuClick('file.new')
    expect(t.logged.join('\n')).toContain("was not sent: the page in the frame has not said hello")
  })
})

describe('the core shows a server', () => {
  it('loads it into the frame and accepts messages from that origin only', async () => {
    const t = setup()
    await t.page.start()
    t.core({ kind: 'show', origin: 'https://demo.example.org' })
    expect(t.frame.src).toBe('https://demo.example.org/')
    expect(t.statuses.at(-1)).toMatchObject({ title: 'Opening…' })
    t.hello()
    expect(t.toFrame()).toMatchObject([{ type: 'welcome', capabilities: ['native-menu', 'actions', 'connect', 'servers'] }])
    expect(t.posted[0]!.origin).toBe('https://demo.example.org')
  })

  it('takes the origin from the address, whatever else is in it', async () => {
    const t = setup()
    await t.page.start()
    t.core({ kind: 'show', origin: 'http://127.0.0.1:51234/some/path?x=1' })
    expect(t.frame.src).toBe('http://127.0.0.1:51234/')
  })

  it('hides the status when the page has loaded, but not for the blank page the frame starts with', async () => {
    const t = setup()
    await t.page.start()
    t.statuses.length = 0
    t.frameListeners.forEach((l) => l())
    expect(t.statuses).toEqual([])
    t.core({ kind: 'show', origin: 'https://demo.example.org' })
    t.frameListeners.forEach((l) => l())
    expect(t.statuses.at(-1)).toBe('hidden')
  })

  it('asks the core for the server list when the page says hello', async () => {
    const t = setup()
    await t.page.start()
    t.core({ kind: 'show', origin: 'https://demo.example.org' })
    t.dispatched.length = 0
    t.hello()
    await tick()
    expect(t.dispatched).toEqual([{ id: CORE_ID, event: TO_CORE, data: { kind: 'want_servers' } }])
    expect(t.statuses.at(-1)).toBe('hidden')
  })

  it('welcomes a page again after it was replaced by another server (a new hello)', async () => {
    const t = setup()
    await t.open()
    t.core({ kind: 'show', origin: 'https://other.example' })
    t.fromFrame({ type: 'action_state', states: { 'file.new': { enabled: false } } }, 'https://other.example')
    expect(t.toFrame().map((m) => m.code)).toEqual(['bad_message']) // not welcomed yet
    t.fromFrame({ type: 'hello', contract: 1 }, 'https://other.example')
    expect(t.toFrame().at(-1).type).toBe('welcome')
  })
})

describe('messages from the frame', () => {
  it('are refused from another window (even with the right origin)', async () => {
    const t = setup()
    await t.open()
    t.fromFrame({ type: 'hello', contract: 1 }, 'https://demo.example.org', { postMessage: () => {} })
    expect(t.posted).toEqual([])
  })

  it('are refused from an origin the core did not ask to show, and logged', async () => {
    const t = setup()
    await t.open()
    t.fromFrame({ type: 'hello', contract: 1 }, 'https://evil.example')
    expect(t.posted).toEqual([])
    expect(t.logged.join('')).toContain('https://evil.example')
  })

  it('are refused before any page was opened', async () => {
    const t = setup()
    await t.page.start()
    t.fromFrame({ type: 'hello', contract: 1 })
    expect(t.posted).toEqual([])
  })

  it('are ignored when they are not text', async () => {
    const t = setup()
    await t.open()
    t.fromFrameRaw({ type: 'hello', contract: 1 }) // the web app sends JSON text; an object is something else
    t.fromFrameRaw(42)
    expect(t.posted).toEqual([])
  })

  it('answer a message that breaks the contract with an error', async () => {
    const t = setup()
    await t.open()
    t.fromFrame('{"type":"hello"')
    expect(t.toFrame().at(-1)).toMatchObject({ type: 'error', code: 'bad_json' })
  })

  it('connect and servers go to the core', async () => {
    const t = setup()
    await t.open()
    t.fromFrame({ type: 'connect', address: 'demo.example.org' })
    t.fromFrame({ type: 'servers', servers: [{ origin: 'https://a.example', label: 'A', custom: false }] })
    await tick()
    expect(t.dispatched.map((d) => d.data.kind)).toEqual(['connect', 'servers'])
    expect(t.dispatched[0]!.data.address).toBe('demo.example.org')
  })

  it('action states change the native menu once, for a whole burst, and only for known actions', async () => {
    const t = setup()
    await t.open()
    t.menus.length = 0
    t.fromFrame({ type: 'action_state', states: { 'file.new': { enabled: false } } })
    t.fromFrame({ type: 'action_state', states: { 'file.open': { label: 'Open a deck…' } } })
    await tick()
    expect(t.menus).toHaveLength(1)
    const items = (t.menus[0] as any[]).flatMap((m) => m.menuItems ?? []).filter((i) => i.id)
    expect(items.find((i) => i.id === 'file.new').isDisabled).toBe(true)
    expect(items.find((i) => i.id === 'file.open').text).toBe('Open a deck…')
  })
})

describe('the native menu', () => {
  it('Quit ends the application itself, not through the page', async () => {
    const t = setup()
    await t.open()
    t.menuClick('file.quit')
    expect(t.calls).toContain('exit')
    expect(t.toFrame()).toEqual([])
  })

  it('an ordinary item becomes an action for the page, About too (macOS has no native About)', async () => {
    const t = setup()
    await t.open()
    t.menuClick('file.new')
    t.menuClick('help.about')
    expect(t.toFrame()).toEqual([
      { type: 'action', action: 'file.new' },
      { type: 'action', action: 'help.about' },
    ])
  })

  it('a click before the page is there is dropped', async () => {
    const t = setup()
    await t.page.start()
    expect(() => t.menuClick('file.new')).not.toThrow()
    expect(t.posted).toEqual([])
  })

  it('a click on something that is not an item of ours is ignored and logged', async () => {
    const t = setup()
    await t.open()
    t.listeners.mainMenuItemClicked!({ detail: { id: 'nope.nope' } })
    expect(t.posted).toEqual([])
    expect(t.logged.join('')).toContain('nope.nope')
  })

  it('a tick-mark item is sent with the target it is turning to, following what the page reported', async () => {
    const t = setup()
    await t.open()
    const checkable = knownActions(MENU).find((a) => a.checkable)
    if (!checkable) return // this app has no tick-mark item
    t.menuClick(checkable.id)
    expect(t.toFrame().at(-1)).toMatchObject({ action: checkable.id, target: 'on' })
    t.fromFrame({ type: 'action_state', states: { [checkable.id]: { checked: true } } })
    t.posted.length = 0
    t.menuClick(checkable.id)
    expect(t.toFrame().at(-1)).toMatchObject({ target: 'off' })
  })

  it('ignores a menu event without an id', async () => {
    const t = setup()
    await t.open()
    t.listeners.mainMenuItemClicked!({ detail: null })
    t.listeners.mainMenuItemClicked!({ detail: { id: 5 } })
    expect(t.posted).toEqual([])
  })
})

describe('other messages of the core', () => {
  it('status shows in the window', async () => {
    const t = setup()
    await t.page.start()
    t.core({ kind: 'status', title: 'Starting Claudia Creates…', error: false })
    t.core({ kind: 'status', title: 'Cannot start', details: 'no python', error: true })
    expect(t.statuses.at(-1)).toEqual({ title: 'Cannot start', details: 'no python', error: true })
  })

  it('servers go to the page when it is there, and nowhere when it is not', async () => {
    const t = setup()
    await t.page.start()
    t.core({ kind: 'servers', servers: [] })
    expect(t.posted).toEqual([])
    await t.open()
    t.core({ kind: 'servers', servers: [{ origin: 'https://a.example', label: 'A', custom: false }] })
    expect(t.toFrame()).toEqual([{ type: 'servers', servers: [{ origin: 'https://a.example', label: 'A', custom: false }] }])
  })

  it('a refused connection goes to the page that asked, with the code', async () => {
    const t = setup()
    await t.open()
    t.core({ kind: 'connect_failed', code: 'wrong_app', message: 'That server runs Claudia Composes.' })
    expect(t.toFrame()).toEqual([{ type: 'connect_failed', code: 'wrong_app', message: 'That server runs Claudia Composes.' }])
  })

  it('a refused connection is said in the window itself when no page is there (--server that fails)', async () => {
    const t = setup()
    await t.page.start()
    t.core({ kind: 'connect_failed', code: 'certificate_invalid', message: 'The certificate is not trusted.' })
    expect(t.statuses.at(-1)).toEqual({ title: 'Cannot connect', details: 'The certificate is not trusted.', error: true })
  })

  it('a code the contract does not know is reported as unreachable', async () => {
    const t = setup()
    await t.open()
    t.core({ kind: 'connect_failed', code: 'weird', message: 'x' })
    expect(t.toFrame()[0]).toMatchObject({ code: 'unreachable' })
  })

  it('a broadcast that is not a message of the core is ignored', async () => {
    const t = setup()
    await t.page.start()
    t.core({ kind: 'dance' })
    t.core(null)
    expect(t.logged.join('')).toContain('not one')
  })
})

describe('knownActions', () => {
  it('lists every item with an id, and which are tick marks', () => {
    const known = knownActions([{ text: 'File', menuItems: [{ id: 'a.b', text: 'x' }, { id: 'c.d', text: 'y', isChecked: false }, { text: '-' }] }])
    expect(known).toEqual([{ id: 'a.b', checkable: false }, { id: 'c.d', checkable: true }])
  })

  it('finds them in the real menu of an app', () => {
    const ids = knownActions(MENU).map((a) => a.id)
    expect(ids).toContain('file.quit')
    expect(ids).toContain('help.about')
    expect(ids).toContain('file.new')
  })
})
