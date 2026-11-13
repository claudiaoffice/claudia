// Moving between the parts of a document window with the keyboard (WCAG 2.1.2 and 2.4.1, BITV 2.0): the menus, the
// toolbar, the document, the panel and the footer. The grid keeps Tab for stepping between cells, as spreadsheets do,
// so F6 and Shift+F6 (`shortcuts.ts`, `regionShortcuts`) are how a keyboard user leaves it and gets past what comes
// before the document. GNOME and Windows both use F6 for this.
//
// `cycleRegions` stays free of the DOM so it can be tested in Node; `windowRegions` is the one function here that
// reads a real page, and the e2e script `regions.cjs` is what exercises it.

/** One part of the window, as far as cycling is concerned. */
export interface Region {
  /** Does this part hold `node`, the element that has focus now? */
  contains(node: unknown): boolean
  /** Put focus into this part. `false` when it has nothing to focus (it is hidden, or empty). */
  enter(): boolean
}

/** Moves focus to the next part after the one holding `active` (the previous one when `backwards`), wrapping round
 * and passing over a part that cannot take focus. Focus outside every part starts at the first part, or at the last
 * going backwards. Returns whether focus went anywhere. */
export function cycleRegions(regions: readonly Region[], active: unknown, backwards: boolean): boolean {
  const count = regions.length
  if (count === 0) return false
  const current = regions.findIndex((region) => region.contains(active))
  const step = backwards ? -1 : 1
  const first = current === -1 ? (backwards ? count - 1 : 0) : current + step
  for (let tried = 0; tried < count; tried++) {
    const region = regions[(((first + tried * step) % count) + count) % count]!
    if (region.enter()) return true
  }
  return false
}

/** What can take focus with the keyboard: not a roving-tabindex item that is not the current one, not a disabled one. */
const FOCUSABLE = [
  'button:not([disabled]):not([tabindex="-1"])',
  'a[href]',
  'input:not([disabled]):not([type="hidden"]):not([tabindex="-1"])',
  'select:not([disabled]):not([tabindex="-1"])',
  'textarea:not([disabled]):not([tabindex="-1"])',
  '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const isShown = (element: Element) => element.getClientRects().length > 0

function entryOf(part: Element): HTMLElement | null {
  const candidates = part.matches(FOCUSABLE) ? [part, ...part.querySelectorAll(FOCUSABLE)] : [...part.querySelectorAll(FOCUSABLE)]
  return (candidates.find(isShown) as HTMLElement | undefined) ?? null
}

/** The parts of a document window: every element marked `data-region`, in the order they come on the page. */
export function windowRegions(root: ParentNode): Region[] {
  return [...root.querySelectorAll('[data-region]')].map((part) => ({
    contains: (node) => node instanceof Node && part.contains(node),
    enter: () => {
      const entry = isShown(part) ? entryOf(part) : null
      entry?.focus()
      return entry !== null
    },
  }))
}
