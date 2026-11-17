// Where a floating panel goes in the window. A panel at a point (a context menu) is pushed back into the window. A panel
// that hangs from a button (the style list) must never cover that button, or the button cannot close it: it stays below
// the button and scrolls when the room is short, unless the button is so low that there is no room worth scrolling in.

/** The size of the window the panel floats in. */
export interface WindowSize {
  w: number
  h: number
}

export interface PanelAsk {
  /** Where the panel was asked to open (its top left corner). */
  x: number
  y: number
  width: number
  /** The height the panel would have if nothing limited it. */
  height: number
  window: WindowSize
  /** The panel hangs from a button that it must not cover. */
  anchored?: boolean
}

export interface Placement {
  left: number
  top: number
  /** The most the panel may be high; its content scrolls beyond that. */
  maxHeight: number
}

/** The space kept free between the panel and the edge of the window. */
export const MARGIN = 8
/** Below this a panel under its button is no use: it goes up over the button's row like any other panel. */
export const LEAST_ROOM_BELOW = 160

/** The place of a panel in the window: its corner and the height beyond which it scrolls. */
export function placePopover({ x, y, width, height, window, anchored = false }: PanelAsk): Placement {
  const left = Math.max(MARGIN, Math.min(x, window.w - width - MARGIN))
  const roomBelow = window.h - y - MARGIN
  if (anchored && roomBelow >= LEAST_ROOM_BELOW) return { left, top: y, maxHeight: roomBelow }
  const top = y + height + MARGIN > window.h ? Math.max(MARGIN, window.h - height - MARGIN) : y
  return { left, top, maxHeight: window.h - 2 * MARGIN }
}
