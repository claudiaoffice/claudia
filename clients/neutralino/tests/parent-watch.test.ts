// The core ends when Neutralino, its parent, is gone (CODE-97, D753). Neutralino does not end its extension, and on
// Windows the link to Neutralino does not always break when Neutralino is killed (seen in CI, 2026-11-25: the core of a
// killed window was still there 90 seconds later), so the core also looks at the process that started it.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { watchParent, watchProcess } from '../src/parent-watch.js'

describe('watchParent', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('says nothing while the parent is there', () => {
    const gone = vi.fn()
    const stop = watchParent({ pid: 4242, parentNow: () => 4242, alive: () => true, onGone: gone })
    vi.advanceTimersByTime(60_000)
    expect(gone).not.toHaveBeenCalled()
    stop()
  })

  it('says once that the parent is gone when its process has ended (Windows: the pid stays the creator\'s)', () => {
    const gone = vi.fn()
    let alive = true
    watchParent({ pid: 4242, parentNow: () => 4242, alive: () => alive, onGone: gone })
    vi.advanceTimersByTime(5_000)
    alive = false
    vi.advanceTimersByTime(5_000)
    vi.advanceTimersByTime(60_000)
    expect(gone).toHaveBeenCalledTimes(1)
    expect(gone.mock.calls[0]![0]).toMatch(/4242/)
  })

  it('says it too when the process was handed to another parent (macOS, Linux: the parent is the init process then)', () => {
    const gone = vi.fn()
    let parent = 4242
    watchParent({ pid: 4242, parentNow: () => parent, alive: () => true, onGone: gone })
    parent = 1
    vi.advanceTimersByTime(5_000)
    expect(gone).toHaveBeenCalledTimes(1)
  })

  it('has no parent to watch when it was started with none (pid 0 or 1): it never says so', () => {
    const gone = vi.fn()
    watchParent({ pid: 1, parentNow: () => 1, alive: () => false, onGone: gone })
    vi.advanceTimersByTime(60_000)
    expect(gone).not.toHaveBeenCalled()
  })

  it('stops looking when told to', () => {
    const gone = vi.fn()
    const stop = watchParent({ pid: 4242, parentNow: () => 4242, alive: () => false, onGone: gone })
    stop()
    vi.advanceTimersByTime(60_000)
    expect(gone).not.toHaveBeenCalled()
  })
})

describe('watchProcess', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('says once that a process that is not the parent is gone: the window, which the core\'s parent (a shell) outlives', () => {
    const gone = vi.fn()
    let alive = true
    watchProcess({ pid: 777, alive: () => alive, onGone: gone })
    vi.advanceTimersByTime(10_000)
    expect(gone).not.toHaveBeenCalled()
    alive = false
    vi.advanceTimersByTime(60_000)
    expect(gone).toHaveBeenCalledTimes(1)
    expect(gone.mock.calls[0]![0]).toMatch(/777/)
  })
})
