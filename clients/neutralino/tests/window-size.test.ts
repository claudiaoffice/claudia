// How big the window is on a screen with display scaling (UX-76, D749): Neutralino takes window sizes in physical pixels
// on Windows, the page thinks in CSS pixels, and the two differ by the scale (devicePixelRatio).
import { describe, expect, it } from 'vitest'
import { WINDOW_WANTED, windowSizeFor } from '../src/window-size.js'

const WANTED = { width: 1280, height: 860, minWidth: 700, minHeight: 500 }

describe('windowSizeFor: the size the window asks for, in physical pixels', () => {
  it('is the configured size at 100% on a large screen', () => {
    expect(windowSizeFor(WANTED, { availWidth: 1920, availHeight: 1040, devicePixelRatio: 1 })).toEqual(WANTED)
  })

  it('keeps the same share of the screen at 200%: twice the pixels (the owner\'s 3840 x 1994 screen)', () => {
    // 1920 x 997 CSS pixels are available there; 1280 x 860 CSS pixels fit, so the window is 2560 x 1720 physical pixels
    expect(windowSizeFor(WANTED, { availWidth: 1920, availHeight: 997, devicePixelRatio: 2 })).toEqual({
      width: 2560,
      height: 1720,
      minWidth: 1400,
      minHeight: 1000,
    })
  })

  it('rounds to whole pixels at 125% and 150%', () => {
    expect(windowSizeFor(WANTED, { availWidth: 2560, availHeight: 1400, devicePixelRatio: 1.25 })).toEqual({
      width: 1600,
      height: 1075,
      minWidth: 875,
      minHeight: 625,
    })
  })

  it('takes at most nine tenths of what the screen has, so that a small screen shows the whole window', () => {
    // 1366 x 728 CSS pixels at 100%: nine tenths are 1229 x 655
    expect(windowSizeFor(WANTED, { availWidth: 1366, availHeight: 728, devicePixelRatio: 1 })).toMatchObject({
      width: 1229,
      height: 655,
    })
  })

  it('never goes below the minimum of the window, and never has a minimum above its size', () => {
    const tiny = windowSizeFor(WANTED, { availWidth: 640, availHeight: 400, devicePixelRatio: 1 })
    expect(tiny.width).toBe(700)
    expect(tiny.height).toBe(500)
    expect(tiny.minWidth).toBeLessThanOrEqual(tiny.width)
    expect(tiny.minHeight).toBeLessThanOrEqual(tiny.height)
  })

  it('treats a missing or nonsensical scale as 100%', () => {
    for (const devicePixelRatio of [0, -1, Number.NaN]) {
      expect(windowSizeFor(WANTED, { availWidth: 1920, availHeight: 1040, devicePixelRatio })).toEqual(WANTED)
    }
  })
})

describe('WINDOW_WANTED', () => {
  it.each(['composes', 'computes', 'creates'])('is what %s says in its config', async (app) => {
    const { readFileSync } = await import('node:fs')
    const config = JSON.parse(readFileSync(new URL(`../apps/${app}/neutralino.config.json`, import.meta.url), 'utf8'))
    const { width, height, minWidth, minHeight } = config.modes.window
    expect({ width, height, minWidth, minHeight }).toEqual(WINDOW_WANTED)
  })
})
