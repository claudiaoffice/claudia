// Click to tag (E5.20, D551): while the chat box has the caret, a click on a thing in the document writes a tag for it
// into the message instead of selecting it. The gate decides, for each mouse event the document is about to get, whether
// it is the beginning, the middle or the end of such a click. It holds no DOM: it is given what is under the pointer and
// whether the box has the caret, so every rule has a test.

/** What to do with an event: let the document have it, keep it from the document, or keep it and take the click as a pick. */
export type Verdict = 'pass' | 'swallow' | { pick: string }

export type PointerKind = 'pointerdown' | 'mousedown' | 'pointerup' | 'mouseup' | 'click' | 'dblclick'

/** The events a click is made of; the gate is to hear all of them. */
export const POINTER_EVENTS: readonly PointerKind[] = ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click', 'dblclick']

/** The attribute that marks what can be picked, with the id of the thing as its value. */
export const THING_ATTRIBUTE = 'data-thing'

/** The id of the thing a node is, or is inside, or `null`. */
export function thingAt(target: unknown): string | null {
  const element = target as { closest?: (selector: string) => Element | null } | null
  const found = element && typeof element.closest === 'function' ? element.closest(`[${THING_ATTRIBUTE}]`) : null
  return found?.getAttribute(THING_ATTRIBUTE) ?? null
}

export class ChatPick {
  /** The thing a click that is going on began on. */
  private began: string | null = null

  constructor(
    private readonly focused: () => boolean,
    private readonly find: (target: unknown) => string | null = thingAt,
  ) {}

  /** Whether a click is going on that the document is not to get. */
  get picking(): boolean {
    return this.began !== null
  }

  handle(type: PointerKind, target: unknown): Verdict {
    if (type === 'pointerdown' || type === 'mousedown') {
      const id = this.focused() ? this.find(target) : null
      // a second press of the same click (`mousedown` after `pointerdown`) is the same click
      if (id === null && this.began !== null && this.find(target) === this.began) return 'swallow'
      this.began = id
      return id === null ? 'pass' : 'swallow'
    }
    if (this.began === null) return 'pass'
    if (type === 'click') {
      const id = this.began
      this.began = null
      return { pick: id }
    }
    return 'swallow'
  }

  /** The box lost the caret: whatever was going on is over. */
  reset(): void {
    this.began = null
  }
}
