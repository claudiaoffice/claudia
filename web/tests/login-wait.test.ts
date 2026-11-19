import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { tooManyTries, useLoginWait } from '~/lib/login-wait'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('what is said after failed logins (D1266)', () => {
  it('says how long to wait, in the singular for one second', () => {
    expect(tooManyTries(1)).toBe('Too many tries. Try again in 1 second.')
    expect(tooManyTries(8)).toBe('Too many tries. Try again in 8 seconds.')
  })

  it('counts down, and says once when the wait is over', () => {
    const wait = useLoginWait()
    expect(wait.waiting.value).toBe(false)
    wait.begin(3)
    expect(wait.waiting.value).toBe(true)
    expect(wait.left.value).toBe(3)
    expect(wait.said.value).toBe('Too many tries. Try again in 3 seconds.')
    vi.advanceTimersByTime(1000)
    expect(wait.left.value).toBe(2)
    expect(wait.said.value).toBe('Too many tries. Try again in 3 seconds.') // the spoken text does not change every second
    vi.advanceTimersByTime(2000)
    expect(wait.left.value).toBe(0)
    expect(wait.waiting.value).toBe(false)
    expect(wait.said.value).toBe('You can try again now.')
  })

  it('starts the wait again when a new one is asked for, and stops its clock when cleared', () => {
    const wait = useLoginWait()
    wait.begin(5)
    vi.advanceTimersByTime(2000)
    wait.begin(2)
    expect(wait.left.value).toBe(2)
    wait.clear()
    expect(wait.waiting.value).toBe(false)
    expect(wait.said.value).toBe('')
    expect(vi.getTimerCount()).toBe(0)
  })

  it('does not wait for a wait of no seconds', () => {
    const wait = useLoginWait()
    wait.begin(0)
    expect(wait.waiting.value).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })
})
