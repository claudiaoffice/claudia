import { describe, expect, it, vi } from 'vitest'
import { nextTick, reactive, watchEffect } from 'vue'
import { ShellBridge, createShellBridge, detectHandler, isApp, tabTitle } from '~/lib/shell-bridge'

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

  it('becomes ready and picks up capabilities from welcome', () => {
    const { sink } = fakeSink()
    const bridge = new ShellBridge('computes', sink)
    expect(bridge.ready).toBe(false)
    bridge.receive(JSON.stringify({ type: 'welcome', contract: 1, shell: { name: 'gtk', platform: 'linux', version: '1' }, capabilities: ['native-menu', 'actions'] }))
    expect(bridge.ready).toBe(true)
    expect(bridge.nativeMenu).toBe(true)
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
    expect(bridge.servers).toEqual([LOCAL, DEMO])
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
})
