import { describe, expect, it } from 'vitest'
import { MAX_SECONDS, PLAN_CHIPS, formatTime, parseTime, stepTime } from '~/lib/show-time'

describe('showing a time (D343)', () => {
  it('writes minutes and seconds, and hours only when there are some', () => {
    expect([0, 5, 60, 125, 3599, 3600, 3725].map(formatTime)).toEqual(['0:00', '0:05', '1:00', '2:05', '59:59', '1:00:00', '1:02:05'])
  })
  it('writes a time that is not whole, or negative, as the whole seconds it is near', () => {
    expect(formatTime(59.6)).toBe('1:00')
    expect(formatTime(-5)).toBe('0:00')
  })
})

describe('reading a time a person typed', () => {
  it.each([
    ['2', 120], // a bare number is minutes: the thing people mean by "give this slide two"
    ['10', 600],
    ['2:30', 150],
    ['0:45', 45],
    ['1:02:03', 3723],
    ['90s', 90],
    ['2m', 120],
    ['1h', 3600],
    ['1m30s', 90],
    [' 3 min ', 180],
    ['2,5', 150], // two and a half minutes, the way a German keyboard writes it
    ['2.5', 150],
  ])('reads %j as %d seconds', (text, seconds) => {
    expect(parseTime(text)).toBe(seconds)
  })
  it.each(['', 'abc', '0', '0:00', '-3', '1:75', '2:5', '25h', '1:2:3:4'])('reads %j as no time', (text) => {
    expect(parseTime(text)).toBeNull()
  })
  it('keeps to a day', () => {
    expect(parseTime('24h')).toBe(MAX_SECONDS)
    expect(parseTime('25h')).toBeNull()
  })
})

describe('the chips and the steps', () => {
  it('offers a few minutes, in seconds', () => {
    expect(PLAN_CHIPS).toEqual([60, 120, 180, 300, 600])
  })
  it('steps by 30 seconds up to two minutes, then by a minute, never below the first step', () => {
    expect(stepTime(null, 1)).toBe(30)
    expect(stepTime(30, 1)).toBe(60)
    expect(stepTime(120, 1)).toBe(180)
    expect(stepTime(180, -1)).toBe(120)
    expect(stepTime(90, -1)).toBe(60)
    expect(stepTime(120, -1)).toBe(90)
    expect(stepTime(30, -1)).toBe(30)
    expect(stepTime(null, -1)).toBeNull()
  })
  it('stops at the day', () => {
    expect(stepTime(MAX_SECONDS, 1)).toBe(MAX_SECONDS)
  })
})
