import { describe, expect, it } from 'vitest'
import { holdPresence, presenceUrl } from '~/lib/presence'

/** A WebSocket that does nothing but record what is done to it, and lets a test close it as a server would. */
class FakeSocket {
  static made: FakeSocket[] = []
  onclose: (() => void) | null = null
  closed = false
  constructor(readonly url: string) {
    FakeSocket.made.push(this)
  }
  close() {
    this.closed = true
  }
  dropped() {
    this.onclose?.()
  }
}

function timers() {
  const waiting: Array<{ run: () => void; ms: number }> = []
  return {
    waiting,
    set: (run: () => void, ms: number) => waiting.push({ run, ms }),
    clear: () => waiting.splice(0),
    next() {
      const first = waiting.shift()
      first?.run()
      return first?.ms
    },
  }
}

describe('presence (D434, D445)', () => {
  it('is the socket address of the server shown', () => {
    expect(presenceUrl('http://127.0.0.1:8760')).toBe('ws://127.0.0.1:8760/api/presence')
    expect(presenceUrl('https://office.example/')).toBe('wss://office.example/api/presence')
  })

  it('holds one socket, comes back after a drop with a growing wait, and lets go for good', () => {
    FakeSocket.made = []
    const clock = timers()
    const release = holdPresence('http://127.0.0.1:8760', {
      WebSocket: FakeSocket as unknown as typeof WebSocket,
      setTimeout: clock.set,
      clearTimeout: clock.clear,
    })
    expect(FakeSocket.made.map((s) => s.url)).toEqual(['ws://127.0.0.1:8760/api/presence'])
    FakeSocket.made[0]!.dropped()
    expect(clock.next()).toBe(1000)
    expect(FakeSocket.made).toHaveLength(2)
    FakeSocket.made[1]!.dropped()
    expect(clock.next()).toBe(2000)
    release()
    expect(FakeSocket.made[2]!.closed).toBe(true)
    FakeSocket.made[2]!.dropped() // the close that letting go causes starts nothing
    expect(clock.waiting).toHaveLength(0)
    expect(FakeSocket.made).toHaveLength(3)
  })

  it('letting go while it waits to come back cancels the wait', () => {
    FakeSocket.made = []
    const clock = timers()
    const release = holdPresence('http://127.0.0.1:8760', {
      WebSocket: FakeSocket as unknown as typeof WebSocket,
      setTimeout: clock.set,
      clearTimeout: clock.clear,
    })
    FakeSocket.made[0]!.dropped()
    expect(clock.waiting).toHaveLength(1)
    release()
    expect(clock.waiting).toHaveLength(0)
    expect(FakeSocket.made).toHaveLength(1)
  })

  it('never waits longer than half a minute', () => {
    FakeSocket.made = []
    const clock = timers()
    holdPresence('http://127.0.0.1:8760', {
      WebSocket: FakeSocket as unknown as typeof WebSocket,
      setTimeout: clock.set,
      clearTimeout: clock.clear,
    })
    let waited = 0
    for (let i = 0; i < 10; i++) {
      FakeSocket.made.at(-1)!.dropped()
      waited = clock.next() ?? 0
    }
    expect(waited).toBe(30000)
  })
})
