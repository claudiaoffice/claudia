import { describe, expect, it } from 'vitest'
import { importBar } from '~/lib/import-progress'

describe('the one bar of an import: sending, reading, opening', () => {
  it('fills the first third with what has been sent', () => {
    expect(importBar('sending', 0.38)).toEqual({ parts: [0.38, 0, 0], now: 0, value: 13, text: 'Sending 38%' })
  })
  it('stands at a full first third once the file is there and Open is waiting', () => {
    expect(importBar('sent', 1)).toEqual({ parts: [1, 0, 0], now: 0, value: 33, text: 'Sent' })
  })
  it('cannot measure reading or opening, so the part being done moves and the value is left out', () => {
    expect(importBar('reading', 1)).toEqual({ parts: [1, 'busy', 0], now: 1, value: null, text: 'Reading' })
    expect(importBar('opening', 1)).toEqual({ parts: [1, 1, 'busy'], now: 2, value: null, text: 'Opening' })
  })
  it('never shows more than was sent, or less than nothing', () => {
    expect(importBar('sending', 1.7).parts[0]).toBe(1)
    expect(importBar('sending', -1).parts[0]).toBe(0)
  })
})
