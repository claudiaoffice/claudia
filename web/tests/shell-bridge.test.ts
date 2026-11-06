import { describe, expect, it, vi } from 'vitest'
import { ShellBridge, createShellBridge, detectHandler } from '~/lib/shell-bridge'

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
})
