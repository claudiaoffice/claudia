import { describe, expect, it, vi } from 'vitest'
import { nextTick, reactive, watchEffect } from 'vue'
import { forgetSetupCode, rememberedSetupCode } from '~/lib/setup-code'
import { FILE_CHUNK_BYTES, ShellBridge, acceptedExtensions, createShellBridge, currentShell, detectHandler, detectParentSink, isApp, isShellOrigin, tabTitle } from '~/lib/shell-bridge'

function fakeSink() {
  const posted: Record<string, unknown>[] = []
  return { sink: { post: (m: Record<string, unknown>) => posted.push(m) }, posted }
}

describe('ShellBridge', () => {
  it('says hello with its contract version and app on construction', () => {
    const { sink, posted } = fakeSink()
    new ShellBridge('composes', sink)
    expect(posted).toEqual([{ type: 'hello', contract: 1, app: 'composes' }])
  })

  it('says whether it is the front page or a document, when it knows (sheet 11)', () => {
    const { sink, posted } = fakeSink()
    new ShellBridge(undefined, sink, 'start')
    new ShellBridge('computes', sink, 'document')
    expect(posted).toEqual([
      { type: 'hello', contract: 1, view: 'start' },
      { type: 'hello', contract: 1, app: 'computes', view: 'document' },
    ])
  })

  it('becomes ready and picks up capabilities from welcome', () => {
    const { sink } = fakeSink()
    const bridge = new ShellBridge('computes', sink)
    expect(bridge.ready).toBe(false)
    bridge.receive(JSON.stringify({ type: 'welcome', contract: 1, shell: { name: 'gtk', platform: 'linux', version: '1' }, capabilities: ['native-menu', 'actions'] }))
    expect(bridge.ready).toBe(true)
    expect(bridge.nativeMenu).toBe(true)
  })

  it("learns the window's own app from welcome (D444), and only one of the three apps", () => {
    const { sink } = fakeSink()
    const bridge = new ShellBridge(undefined, sink)
    expect(bridge.windowApp).toBeNull()
    const shell = { name: 'gtk', platform: 'linux', version: '1' }
    bridge.receive(JSON.stringify({ type: 'welcome', contract: 1, shell, capabilities: [], app: 'composes' }))
    expect(bridge.windowApp).toBe('composes')
    bridge.receive(JSON.stringify({ type: 'welcome', contract: 1, shell, capabilities: [], app: 'paint' }))
    expect(bridge.windowApp).toBeNull()
    bridge.receive(JSON.stringify({ type: 'welcome', contract: 1, shell, capabilities: [] }))
    expect(bridge.windowApp).toBeNull()
  })

  it("keeps the setup code of the desktop app's own server for the settings pages (D1373)", () => {
    forgetSetupCode()
    const { sink } = fakeSink()
    const bridge = new ShellBridge(undefined, sink, 'start')
    const shell = { name: 'gtk', platform: 'linux', version: '1' }
    bridge.receive(JSON.stringify({ type: 'welcome', contract: 1, shell, capabilities: [] }))
    expect(rememberedSetupCode()).toBeNull()
    bridge.receive(JSON.stringify({ type: 'welcome', contract: 1, shell, capabilities: [], setup_code: 42 }))
    expect(rememberedSetupCode()).toBeNull()
    bridge.receive(JSON.stringify({ type: 'welcome', contract: 1, shell, capabilities: [], setup_code: 'K7QM-4TXR-92HB' }))
    expect(rememberedSetupCode()).toEqual({ code: 'K7QM-4TXR-92HB', from: 'app' })
    forgetSetupCode()
  })

  it('dispatches an action message to every registered handler, with its target', () => {
    const { sink } = fakeSink()
    const bridge = new ShellBridge('composes', sink)
    const calls: Array<[string, string | undefined]> = []
    bridge.onAction((id, target) => calls.push([id, target]))
    bridge.receive(JSON.stringify({ type: 'action', action: 'view.page', target: 'on' }))
    expect(calls).toEqual([['view.page', 'on']])
  })

  it('onAction returns a remover', () => {
    const { sink } = fakeSink()
    const bridge = new ShellBridge('composes', sink)
    const handler = vi.fn()
    const remove = bridge.onAction(handler)
    remove()
    bridge.receive(JSON.stringify({ type: 'action', action: 'edit.undo' }))
    expect(handler).not.toHaveBeenCalled()
  })

  it('ignores text that is not JSON instead of throwing', () => {
    const { sink } = fakeSink()
    const bridge = new ShellBridge('composes', sink)
    expect(() => bridge.receive('not json')).not.toThrow()
  })

  it('records the last error message, without throwing', () => {
    const { sink } = fakeSink()
    const bridge = new ShellBridge('composes', sink)
    bridge.receive(JSON.stringify({ type: 'error', code: 'unknown_action', message: 'no such action: x' }))
    expect(bridge.lastError).toBe('unknown_action: no such action: x')
  })

  it('reportStates does nothing before the shell says welcome (nobody is listening yet)', () => {
    const { sink, posted } = fakeSink()
    const bridge = new ShellBridge('composes', sink)
    bridge.reportStates({ 'edit.undo': { enabled: false } })
    expect(posted).toHaveLength(1) // only the hello
  })

  it('reportStates sends only what changed since the last report', () => {
    const { sink, posted } = fakeSink()
    const bridge = new ShellBridge('composes', sink)
    bridge.receive(JSON.stringify({ type: 'welcome', contract: 1, shell: { name: 'gtk', platform: 'linux', version: '1' }, capabilities: [] }))
    bridge.reportStates({ 'edit.undo': { enabled: false }, 'edit.redo': { enabled: false } })
    bridge.reportStates({ 'edit.undo': { enabled: true }, 'edit.redo': { enabled: false } })
    expect(posted[2]).toEqual({ type: 'action_state', states: { 'edit.undo': { enabled: true } } })
  })

  it('reportStates sends nothing, and posts nothing, when nothing changed', () => {
    const { sink, posted } = fakeSink()
    const bridge = new ShellBridge('composes', sink)
    bridge.receive(JSON.stringify({ type: 'welcome', contract: 1, shell: { name: 'gtk', platform: 'linux', version: '1' }, capabilities: [] }))
    bridge.reportStates({ 'edit.undo': { enabled: false } })
    bridge.reportStates({ 'edit.undo': { enabled: false } })
    expect(posted).toHaveLength(2) // hello, and the one real action_state
  })
})

const WELCOME = (capabilities: string[]) =>
  JSON.stringify({ type: 'welcome', contract: 1, shell: { name: 'gtk', platform: 'linux', version: '1' }, capabilities })
const LOCAL = { origin: 'http://127.0.0.1:41233', label: 'This computer', custom: true, local: true }
const DEMO = { origin: 'https://demo.example.org:8420', label: 'Demo', custom: false }

describe('ShellBridge without an app yet', () => {
  it('says hello without an app when the page does not know which app its server runs', () => {
    const { sink, posted } = fakeSink()
    new ShellBridge(undefined, sink)
    expect(posted).toEqual([{ type: 'hello', contract: 1 }])
  })
  it('knows the three apps', () => {
    expect(['composes', 'computes', 'creates'].every(isApp)).toBe(true)
    expect([isApp('claudia'), isApp(''), isApp(undefined)]).toEqual([false, false, false])
  })
})

describe('ShellBridge connecting to another server', () => {
  it('cannot connect before welcome, or when the shell does not offer it', () => {
    const { sink } = fakeSink()
    const bridge = new ShellBridge('computes', sink)
    expect(bridge.canConnect).toBe(false)
    bridge.receive(WELCOME(['native-menu']))
    expect(bridge.canConnect).toBe(false)
    expect(bridge.hasServerList).toBe(false)
  })
  it('posts the address as it was typed', () => {
    const { sink, posted } = fakeSink()
    const bridge = new ShellBridge('computes', sink)
    bridge.receive(WELCOME(['connect', 'servers']))
    expect(bridge.canConnect).toBe(true)
    bridge.connect('demo.example.org:8420')
    expect(posted.at(-1)).toEqual({ type: 'connect', address: 'demo.example.org:8420' })
  })
  it('tells whoever listens why the shell refused, and listeners can be removed', () => {
    const { sink } = fakeSink()
    const bridge = new ShellBridge('computes', sink)
    const seen: Array<[string, string]> = []
    const remove = bridge.onConnectFailed((code, message) => seen.push([code, message]))
    bridge.receive(JSON.stringify({ type: 'connect_failed', code: 'wrong_app', message: 'That server runs Claudia Composes.' }))
    remove()
    bridge.receive(JSON.stringify({ type: 'connect_failed', code: 'unreachable', message: 'Could not reach x.' }))
    expect(seen).toEqual([['wrong_app', 'That server runs Claudia Composes.']])
  })
})

describe('ShellBridge server list', () => {
  it('has no list until the shell sends one, then keeps only well-formed entries', () => {
    const { sink } = fakeSink()
    const bridge = new ShellBridge('computes', sink)
    expect(bridge.servers).toBeNull()
    bridge.receive(JSON.stringify({ type: 'servers', servers: [LOCAL, DEMO, { origin: 3 }, 'x'] }))
    expect(bridge.servers).toEqual([{ ...LOCAL, label: 'Private on this computer' }, DEMO])
  })
  it('never sends a list before the shell has sent its own (an empty page must not wipe what the shell keeps)', () => {
    const { sink, posted } = fakeSink()
    const bridge = new ShellBridge('computes', sink)
    bridge.receive(WELCOME(['servers']))
    bridge.sendServers([DEMO])
    expect(posted.filter((m) => m.type === 'servers')).toEqual([])
  })
  it('sends a changed list back and shows it at once', () => {
    const { sink, posted } = fakeSink()
    const bridge = new ShellBridge('computes', sink)
    bridge.receive(WELCOME(['servers']))
    bridge.receive(JSON.stringify({ type: 'servers', servers: [LOCAL, DEMO] }))
    const renamed = [LOCAL, { ...DEMO, label: 'Mine', custom: true }]
    bridge.sendServers(renamed)
    expect(posted.at(-1)).toEqual({ type: 'servers', servers: renamed })
    expect(bridge.servers).toEqual(renamed)
  })
  it('sends nothing to a shell that does not keep the list', () => {
    const { sink, posted } = fakeSink()
    const bridge = new ShellBridge('computes', sink)
    bridge.receive(WELCOME(['native-menu']))
    bridge.receive(JSON.stringify({ type: 'servers', servers: [DEMO] }))
    bridge.sendServers([DEMO])
    expect(posted.filter((m) => m.type === 'servers')).toEqual([])
  })
})

describe('detectHandler', () => {
  it('is null without window.webkit.messageHandlers.claudia', () => {
    expect(detectHandler({} as any)).toBeNull()
  })
  it('posts stringified JSON through the handler it finds', () => {
    const postMessage = vi.fn()
    const handler = detectHandler({ webkit: { messageHandlers: { claudia: { postMessage } } } } as any)
    handler!.post({ type: 'hello', contract: 1, app: 'composes' })
    expect(postMessage).toHaveBeenCalledWith(JSON.stringify({ type: 'hello', contract: 1, app: 'composes' }))
  })
})

describe('createShellBridge', () => {
  it('without a handler, is never ready and nativeMenu stays false, but nothing throws', () => {
    const bridge = createShellBridge('composes', null)
    expect(bridge.ready).toBe(false)
    expect(bridge.nativeMenu).toBe(false)
    bridge.reportStates({ 'edit.undo': { enabled: true } })
    bridge.detach()
  })

  it('with a handler, registers window.__claudiaShell.receive and detach() removes it again', () => {
    const postMessage = vi.fn()
    const g: any = { webkit: { messageHandlers: { claudia: { postMessage } } } }
    const bridge = createShellBridge('composes', { post: (m) => g.webkit.messageHandlers.claudia.postMessage(JSON.stringify(m)) })
    expect(typeof (globalThis as any).__claudiaShell?.receive).toBe('function')
    bridge.detach()
    expect((globalThis as any).__claudiaShell).toBeUndefined()
  })

  it("detach() leaves another bridge's global alone", () => {
    const a = createShellBridge('composes', { post: () => {} })
    const b = createShellBridge('computes', { post: () => {} })
    a.detach() // a is not the current owner any more (b is) — must not remove b's handler
    expect(typeof (globalThis as any).__claudiaShell?.receive).toBe('function')
    b.detach()
  })

  it("wrap lets a template effect reading shell.nativeMenu re-run on welcome, with no other trigger", async () => {
    // Real delivery is never this synchronous (the shell's reply to `hello` is always a later turn of the event
    // loop, a GTK/WebKit IPC round trip away) — it is simulated here the same way `webpage.py`'s `send()` reaches
    // the page: calling the closure `createShellBridge` registered as `window.__claudiaShell.receive`, once it
    // exists, exactly as a real shell would, not through the `hello` sink (which fires too early, mid-construction,
    // for that global to be there yet).
    const bridge = createShellBridge('composes', { post: () => {} }, (b) => reactive(b) as typeof b)
    const seen: boolean[] = []
    // Stands in for `<MenuBar :class="{ hidden: shell.nativeMenu }">`: a Vue effect that reads `nativeMenu` and is
    // expected to re-run *because that changed*, with nothing else prompting a render in between. Reading
    // `bridge.nativeMenu` straight after `welcome` (no watchEffect) would pass even on the old, broken code — a
    // bare read is always live — so this only catches the bug if Vue's dependency tracking is actually wired up.
    watchEffect(() => seen.push(bridge.nativeMenu))
    ;(globalThis as any).__claudiaShell.receive(
      JSON.stringify({ type: 'welcome', contract: 1, shell: { name: 'gtk', platform: 'linux', version: '1' }, capabilities: ['native-menu', 'actions'] }),
    )
    await nextTick()
    expect(seen).toEqual([false, true])
    bridge.detach()
  })
})

describe('tabTitle', () => {
  it('names the app that is actually open, not a one-size-fits-all default', () => {
    expect(tabTitle('composes')).toBe('Claudia Composes')
    expect(tabTitle('computes')).toBe('Claudia Computes')
    expect(tabTitle('creates')).toBe('Claudia Creates')
  })

  it('falls back to the generic title before a document is open', () => {
    expect(tabTitle(undefined)).toBe('Claudia')
  })

  it('falls back to the generic title for anything that is not one of the three known apps', () => {
    expect(tabTitle('')).toBe('Claudia')
    expect(tabTitle('bogus')).toBe('Claudia')
  })

  // WCAG 2.4.2 (BITV 2.0): a title says what the page is. Two tabs of the same app are told apart by the document.
  it('puts the document first when one is open, so two tabs of the same app differ', () => {
    expect(tabTitle('computes', 'budget 2027')).toBe('budget 2027 – Claudia Computes')
    expect(tabTitle('creates', 'kickoff')).toBe('kickoff – Claudia Creates')
  })

  it('names just the app for an empty or missing document name', () => {
    expect(tabTitle('composes', '')).toBe('Claudia Composes')
    expect(tabTitle('composes', undefined)).toBe('Claudia Composes')
  })

  it('does not put a document name on the generic title', () => {
    expect(tabTitle(undefined, 'budget 2027')).toBe('Claudia')
  })
})

/** A window that has a parent, as a page in a Neutralino shell's frame does. */
function framedWindow() {
  const parent = { postMessage: vi.fn() }
  const listeners = new Set<(event: any) => void>()
  const win: any = {
    parent,
    addEventListener: (_type: string, listener: (event: any) => void) => listeners.add(listener),
    removeEventListener: (_type: string, listener: (event: any) => void) => listeners.delete(listener),
  }
  const deliver = (event: { source: unknown; origin: string; data: unknown }) => listeners.forEach((l) => l(event))
  return { win, parent, listeners, deliver }
}

describe('isShellOrigin', () => {
  it('accepts a Neutralino shell page (plain http, on this computer, any port)', () => {
    expect(isShellOrigin('http://127.0.0.1:51234')).toBe(true)
    expect(isShellOrigin('http://localhost:8080')).toBe(true)
  })

  it('refuses https, other hosts, and rubbish', () => {
    expect(isShellOrigin('https://127.0.0.1:51234')).toBe(false)
    expect(isShellOrigin('http://evil.example')).toBe(false)
    expect(isShellOrigin('http://127.0.0.1.evil.example')).toBe(false)
    expect(isShellOrigin('null')).toBe(false)
    expect(isShellOrigin('')).toBe(false)
  })
})

describe('detectParentSink', () => {
  it('is null for a top window (a browser tab, or the GTK shell)', () => {
    const top: any = {}
    top.parent = top
    expect(detectParentSink(top)).toBeNull()
    expect(detectParentSink({} as any)).toBeNull()
  })

  it('posts each message to the parent window, as JSON text', () => {
    const { win, parent } = framedWindow()
    detectParentSink(win)!.post({ type: 'hello', contract: 1 })
    expect(parent.postMessage).toHaveBeenCalledWith('{"type":"hello","contract":1}', '*')
  })

  it('passes on text from the parent when it is a shell page on this computer', () => {
    const { win, parent, deliver } = framedWindow()
    const received: string[] = []
    detectParentSink(win)!.listen!((raw) => received.push(raw))
    deliver({ source: parent, origin: 'http://127.0.0.1:5000', data: '{"type":"welcome"}' })
    expect(received).toEqual(['{"type":"welcome"}'])
  })

  it('ignores a message from another window, from another origin, or that is not text', () => {
    const { win, parent, deliver } = framedWindow()
    const received: string[] = []
    detectParentSink(win)!.listen!((raw) => received.push(raw))
    deliver({ source: {}, origin: 'http://127.0.0.1:5000', data: 'x' })
    deliver({ source: parent, origin: 'https://evil.example', data: 'x' })
    deliver({ source: parent, origin: 'http://127.0.0.1:5000', data: { type: 'welcome' } })
    expect(received).toEqual([])
  })

  it('stops listening when told to', () => {
    const { win, listeners } = framedWindow()
    const stop = detectParentSink(win)!.listen!(() => {})
    expect(listeners.size).toBe(1)
    stop()
    expect(listeners.size).toBe(0)
  })
})

describe('createShellBridge with a sink that listens', () => {
  it('feeds what the sink hears into the bridge, and stops on detach', () => {
    let feed: ((raw: string) => void) | null = null
    const stop = vi.fn()
    const sink = { post: () => {}, listen: (receive: (raw: string) => void) => ((feed = receive), stop) }
    const bridge = createShellBridge('composes', sink)
    feed!(JSON.stringify({ type: 'welcome', contract: 1, shell: { name: 'neutralino', platform: 'macos', version: '1' }, capabilities: ['native-menu'] }))
    expect(bridge.nativeMenu).toBe(true)
    bridge.detach()
    expect(stop).toHaveBeenCalled()
  })
})

describe('files through the shell (D501, D502)', () => {
  const shell = { name: 'gtk', platform: 'linux', version: '1' }
  function welcomed(capabilities = ['native-menu', 'actions', 'files']) {
    const { sink, posted } = fakeSink()
    const bridge = new ShellBridge('composes', sink)
    bridge.receive(JSON.stringify({ type: 'welcome', contract: 1, shell, capabilities }))
    posted.length = 0
    return { bridge, posted, say: (m: Record<string, unknown>) => bridge.receive(JSON.stringify(m)) }
  }
  const b64 = (text: string) => btoa(text)

  it('handles files only when the shell says so', () => {
    expect(welcomed().bridge.handlesFiles).toBe(true)
    expect(welcomed(['native-menu']).bridge.handlesFiles).toBe(false)
    expect(new ShellBridge('composes', fakeSink().sink).handlesFiles).toBe(false)
  })

  it('asks for a file with the extensions, and makes a File of the pieces that come back', async () => {
    const { bridge, posted, say } = welcomed()
    const picking = bridge.pickFile(['docx', 'odt'], 'Open a File')
    expect(posted).toEqual([{ type: 'pick_file', request: expect.stringMatching(/^[a-z][a-z0-9-]*$/), accept: ['docx', 'odt'], title: 'Open a File' }])
    const request = posted[0]!.request as string
    say({ type: 'file_result', request, outcome: 'picked', name: 'budget.docx', size: 11 })
    say({ type: 'file_chunk', request, index: 0, data: b64('hello ') })
    say({ type: 'file_chunk', request, index: 1, data: b64('world') })
    say({ type: 'file_done', request, chunks: 2 })
    const file = await picking
    expect(file?.name).toBe('budget.docx')
    expect(await file?.text()).toBe('hello world')
  })

  it('gives null when the person cancelled, and an error with the shell\'s words when it failed', async () => {
    const { bridge, posted, say } = welcomed()
    const cancelled = bridge.pickFile([])
    say({ type: 'file_result', request: posted[0]!.request, outcome: 'cancelled' })
    expect(await cancelled).toBeNull()
    const failing = bridge.pickFile([])
    say({ type: 'file_result', request: posted[1]!.request, outcome: 'failed', message: 'permission denied' })
    await expect(failing).rejects.toThrow('permission denied')
  })

  it('refuses a file that lost a piece or came incomplete', async () => {
    const { bridge, posted, say } = welcomed()
    const gap = bridge.pickFile([])
    const request = posted[0]!.request
    say({ type: 'file_result', request, outcome: 'picked', name: 'a.txt', size: 4 })
    say({ type: 'file_chunk', request, index: 1, data: b64('ab') })
    await expect(gap).rejects.toThrow(/missing/)
    const short = bridge.pickFile([])
    const second = posted[1]!.request
    say({ type: 'file_result', request: second, outcome: 'picked', name: 'a.txt', size: 4 })
    say({ type: 'file_chunk', request: second, index: 0, data: b64('ab') })
    say({ type: 'file_done', request: second, chunks: 1 })
    await expect(short).rejects.toThrow(/whole/)
  })

  it('hands a file the person dropped on the window to whoever listens (D505)', () => {
    const { bridge, say } = welcomed()
    const got: File[] = []
    const stop = bridge.onFileOffered((file) => got.push(file))
    say({ type: 'offer_file', request: 'drop-1', name: 'budget.ods', size: 11 })
    say({ type: 'file_chunk', request: 'drop-1', index: 0, data: b64('hello ') })
    say({ type: 'file_chunk', request: 'drop-1', index: 1, data: b64('world') })
    say({ type: 'file_done', request: 'drop-1', chunks: 2 })
    expect(got.map((file) => file.name)).toEqual(['budget.ods'])
    stop()
    say({ type: 'offer_file', request: 'drop-2', name: 'more.ods', size: 1 })
    say({ type: 'file_chunk', request: 'drop-2', index: 0, data: b64('x') })
    say({ type: 'file_done', request: 'drop-2', chunks: 1 })
    expect(got).toHaveLength(1)
  })

  it('drops an offered file that is too large or arrives short, without throwing', () => {
    const { bridge, say } = welcomed()
    const got: File[] = []
    bridge.onFileOffered((file) => got.push(file))
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    say({ type: 'offer_file', request: 'drop-1', name: 'huge.ods', size: 200 * 1024 * 1024 })
    say({ type: 'file_done', request: 'drop-1', chunks: 0 })
    say({ type: 'offer_file', request: 'drop-2', name: 'short.ods', size: 4 })
    say({ type: 'file_chunk', request: 'drop-2', index: 0, data: b64('ab') })
    say({ type: 'file_done', request: 'drop-2', chunks: 1 })
    expect(got).toEqual([])
    expect(warn).toHaveBeenCalledTimes(2)
    warn.mockRestore()
  })

  it('ignores answers to a request it did not make', () => {
    const { say } = welcomed()
    expect(() => say({ type: 'file_result', request: 'nobody', outcome: 'saved', path: '/x' })).not.toThrow()
  })

  it('sends a file to save in pieces no message is too large for, and says where the shell saved it', async () => {
    const { bridge, posted, say } = welcomed()
    const bytes = new Uint8Array(FILE_CHUNK_BYTES * 2 + 5).map((_, i) => i % 251)
    const saving = bridge.saveFile('budget.xlsx', new Blob([bytes], { type: 'application/vnd.ms-excel' }))
    await vi.waitFor(() => expect(posted.at(-1)?.type).toBe('file_done'))
    const [begin, ...rest] = posted
    expect(begin).toMatchObject({ type: 'save_file', name: 'budget.xlsx', size: bytes.length, mime: 'application/vnd.ms-excel' })
    expect(begin).not.toHaveProperty('purpose')
    const chunks = rest.filter((m) => m.type === 'file_chunk')
    expect(chunks.map((m) => m.index)).toEqual([0, 1, 2])
    for (const chunk of chunks) expect(JSON.stringify(chunk).length).toBeLessThan(64 * 1024)
    const joined = chunks.map((m) => atob(m.data as string)).join('')
    expect(Uint8Array.from(joined, (c) => c.charCodeAt(0))).toEqual(bytes)
    expect(rest.at(-1)).toEqual({ type: 'file_done', request: begin!.request, chunks: 3 })
    say({ type: 'file_result', request: begin!.request, outcome: 'saved', path: '/home/ann/Documents/budget.xlsx' })
    expect(await saving).toEqual({ kind: 'saved', path: '/home/ann/Documents/budget.xlsx' })
  })

  it('hands a PDF over to print it: the shell opens it in the computer\'s viewer (D502)', async () => {
    const { bridge, posted, say } = welcomed()
    const opening = bridge.saveFile('pages.pdf', new Blob(['%PDF'], { type: 'application/pdf' }), 'print')
    await vi.waitFor(() => expect(posted.at(-1)?.type).toBe('file_done'))
    expect(posted[0]).toMatchObject({ type: 'save_file', purpose: 'print' })
    say({ type: 'file_result', request: posted[0]!.request, outcome: 'opened', path: '/tmp/pages.pdf' })
    expect(await opening).toEqual({ kind: 'opened', path: '/tmp/pages.pdf' })
  })

  it('a cancelled Save dialog is no error', async () => {
    const { bridge, posted, say } = welcomed()
    const saving = bridge.saveFile('a.txt', new Blob(['x']))
    await vi.waitFor(() => expect(posted.at(-1)?.type).toBe('file_done'))
    say({ type: 'file_result', request: posted[0]!.request, outcome: 'cancelled' })
    expect(await saving).toEqual({ kind: 'cancelled' })
  })
})

describe('acceptedExtensions', () => {
  it('keeps the extensions of an accept value, without the dot, and leaves out MIME types', () => {
    expect(acceptedExtensions('.docx, .ODT,image/png,.claudia,.docx')).toEqual(['docx', 'odt', 'claudia'])
    expect(acceptedExtensions('image/*')).toEqual([])
    expect(acceptedExtensions('.a b,.toolongextension123')).toEqual([])
  })
})

describe('currentShell', () => {
  it('is the newest bridge whose shell has said welcome, and forgets one that is detached', () => {
    const sink = { post: () => {}, listen: () => () => {} }
    expect(currentShell()).toBeNull()
    const first = createShellBridge('composes', sink)
    expect(currentShell()).toBeNull() // no welcome yet
    first.receive(JSON.stringify({ type: 'welcome', contract: 1, shell: { name: 'gtk', platform: 'linux', version: '1' }, capabilities: ['files'] }))
    expect(currentShell()).toBe(first)
    const second = createShellBridge('composes', sink)
    second.receive(JSON.stringify({ type: 'welcome', contract: 1, shell: { name: 'gtk', platform: 'linux', version: '1' }, capabilities: [] }))
    expect(currentShell()).toBe(second)
    second.detach()
    expect(currentShell()).toBe(first)
    first.detach()
    expect(currentShell()).toBeNull()
  })
})
