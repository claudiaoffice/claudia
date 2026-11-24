// How big the window is on a screen with display scaling (UX-76, D749). Browser-safe: no Node import.
//
// The configs (`apps/<app>/neutralino.config.json`) say 1280 x 860 and 700 x 500 as if they were CSS pixels. Neutralino
// on Windows takes sizes in physical pixels: at a display scale of 200% the window opened at 640 x 430 CSS pixels and
// showed a page that is too small for it. So the page asks for the size again once it runs, with the scale applied
// (shell-page.ts, `fitWindow`), and takes at most nine tenths of the screen so that a small screen shows the whole window.

export interface WindowSize {
  width: number
  height: number
  minWidth: number
  minHeight: number
}

/** What the page can tell about the screen the window is on, in CSS pixels (`window.screen`, `window.devicePixelRatio`). */
export interface ScreenSize {
  availWidth: number
  availHeight: number
  devicePixelRatio: number
}

/** The window of every app, in CSS pixels: what `modes.window` of each `apps/<app>/neutralino.config.json` says
 * (tests/window-size.test.ts keeps the two together). */
export const WINDOW_WANTED: WindowSize = { width: 1280, height: 860, minWidth: 700, minHeight: 500 }

/** The share of the screen the window may take. */
const SHARE = 0.9

/** The size to ask Neutralino for, in physical pixels, when `wanted` is in CSS pixels. */
export function windowSizeFor(wanted: WindowSize, screen: ScreenSize): WindowSize {
  const scale = screen.devicePixelRatio > 0 ? screen.devicePixelRatio : 1
  const fit = (size: number, available: number, least: number): number => Math.max(Math.min(size, Math.floor(available * SHARE)), least)
  const physical = (cssPixels: number): number => Math.round(cssPixels * scale)
  return {
    width: physical(fit(wanted.width, screen.availWidth, wanted.minWidth)),
    height: physical(fit(wanted.height, screen.availHeight, wanted.minHeight)),
    minWidth: physical(wanted.minWidth),
    minHeight: physical(wanted.minHeight),
  }
}
