// The show (E10.2): which slide is on the screen, the overview, a blank screen, the typed slide number and the clock of the
// talk. It holds no slides of its own, only ids, planned times and notes frozen when the show started (D292), and no
// DOM: the component draws it and feeds it keys and the time (`now`, in seconds), so every rule is tested in Node.
//
// Showing is read-only and local (D291): nothing here writes to the document, takes a lock or leaves a step in the
// history.
import type { KeyLike } from './shortcuts'

export interface ShowSlide {
  id: string
  /** The planned time in whole seconds, or null (D294). */
  seconds: number | null
  /** The speaker notes, Markdown (D293). */
  notes: string
}

/** What a key means in the show. `up` and `down` move a row in the overview and a slide outside it. */
export type ShowCommand = 'next' | 'prev' | 'up' | 'down' | 'first' | 'last' | 'blank' | 'overview' | 'swap' | 'exit' | 'confirm' | 'fullscreen'
export type ShowAction = ShowCommand | { digit: string }

const KEYS: Record<string, ShowCommand> = {
  ArrowRight: 'next',
  PageDown: 'next',
  ' ': 'next',
  n: 'next',
  ArrowDown: 'down',
  ArrowLeft: 'prev',
  PageUp: 'prev',
  Backspace: 'prev',
  ArrowUp: 'up',
  Home: 'first',
  End: 'last',
  b: 'blank',
  '.': 'blank',
  g: 'overview',
  p: 'swap',
  Escape: 'exit',
  Enter: 'confirm',
  f: 'fullscreen',
}

/** What a key does in the show, or null for one that is not the show's (a chord with Ctrl, Alt or the Mac's Command
 * is the browser's or the shell's, and is left to it). */
export function showAction(event: KeyLike): ShowAction | null {
  if (event.ctrlKey || event.metaKey || event.altKey) return null
  if (/^[0-9]$/.test(event.key)) return { digit: event.key }
  return KEYS[event.key] ?? KEYS[event.key.toLowerCase()] ?? null
}

/** How many steps the document has taken since the show started, if both are revisions of one line (`main:12`). It
 * is what "Changes since you started: N" says (D292); across lines, or without a revision, nobody can tell. */
export function changesSince(started: string | null, now: string | null): number | null {
  const a = /^(.*):(\d+)$/.exec(started ?? '')
  const b = /^(.*):(\d+)$/.exec(now ?? '')
  return a && b && a[1] === b[1] ? Math.abs(Number(b[2]) - Number(a[2])) : null
}

/** Digits typed one after the other are one number; ones typed this many seconds apart are not. */
const DIGIT_PAUSE = 3

export interface ShowOptions {
  /** The slide to start on, by place. */
  from: number
  /** The time of the start, in seconds. */
  now: number
  view?: 'audience' | 'presenter'
  /** How many slides the overview has in a row, for the arrows up and down. */
  columns?: number
}

export class Show {
  slides: ShowSlide[]
  index: number
  view: 'audience' | 'presenter'
  blank = false
  ended = false
  overview = false
  cursor: number
  typed = ''
  private typedAt = 0
  private readonly startedAt: number
  private enteredAt: number
  private readonly spent: Record<string, number> = {}
  private readonly columns: number

  constructor(slides: ShowSlide[], options: ShowOptions) {
    this.slides = slides
    this.index = Math.min(Math.max(options.from, 0), Math.max(slides.length - 1, 0))
    this.cursor = this.index
    this.view = options.view ?? 'audience'
    this.columns = options.columns ?? 4
    this.startedAt = this.enteredAt = options.now
  }

  get current(): ShowSlide {
    return this.slides[this.index]!
  }

  /** The slide after this one, or null at the last. */
  get next(): ShowSlide | null {
    return this.slides[this.index + 1] ?? null
  }

  /** The planned total: the slides' times added up, and how many slides have one and how many do not. */
  get planned(): { seconds: number; planned: number; unplanned: number } {
    const times = this.slides.map((s) => s.seconds).filter((s): s is number => s !== null)
    return { seconds: times.reduce((a, b) => a + b, 0), planned: times.length, unplanned: this.slides.length - times.length }
  }

  /** The planned time of the slide that is shown. */
  get slidePlan(): number | null {
    return this.current.seconds
  }

  /** Take in a newer copy of the slides, between two of them (D292): the slide that is shown stays shown, found by its id
   * (the nearest place if it is gone), and the clock and what was spent on each slide go on. From the end screen, a
   * slide that came in after the last one is the one to show next. */
  update(slides: ShowSlide[]): void {
    const was = this.current
    const afterLast = this.ended ? this.slides.length : -1
    this.slides = slides
    const found = slides.findIndex((slide) => slide.id === was.id)
    this.index = found >= 0 ? found : Math.min(this.index, slides.length - 1)
    if (this.ended && slides.length > afterLast) {
      this.ended = false
      this.index = Math.min(afterLast, slides.length - 1)
    }
    this.cursor = this.index
  }

  // ------------------------------------------------------------------------------ keys
  /** Do what a key says. `'exit'` when the show is over. */
  press(command: ShowCommand, now: number): 'exit' | null {
    if (command === 'fullscreen') return null // the window's, not the show's
    if (command === 'exit') return this.leave()
    if (command === 'swap') this.view = this.view === 'audience' ? 'presenter' : 'audience'
    else if (command === 'overview') this.toggleOverview()
    else if (this.overview) this.inOverview(command, now)
    else return this.step(command, now)
    return null
  }

  /** A digit of a slide number. */
  digit(digit: string, now: number): void {
    this.typed = now - this.typedAt > DIGIT_PAUSE ? digit : this.typed + digit
    this.typedAt = now
  }

  private leave(): 'exit' | null {
    if (this.typed) this.typed = ''
    else if (this.overview) this.overview = false
    else return 'exit'
    return null
  }

  private toggleOverview(): void {
    this.overview = !this.overview
    this.cursor = this.index
  }

  private jump(now: number): boolean {
    const wanted = Number(this.typed)
    this.typed = ''
    if (!Number.isInteger(wanted) || wanted < 1 || wanted > this.slides.length) return false
    this.go(wanted - 1, now)
    this.overview = false
    return true
  }

  private inOverview(command: ShowCommand, now: number): void {
    const last = this.slides.length - 1
    switch (command) {
      case 'next':
        this.cursor = Math.min(last, this.cursor + 1)
        break
      case 'prev':
        this.cursor = Math.max(0, this.cursor - 1)
        break
      case 'down':
        if (this.cursor + this.columns <= last) this.cursor += this.columns
        break
      case 'up':
        if (this.cursor - this.columns >= 0) this.cursor -= this.columns
        break
      case 'first':
        this.cursor = 0
        break
      case 'last':
        this.cursor = last
        break
      case 'confirm':
        if (!this.typed || !this.jump(now)) {
          this.typed = ''
          this.go(this.cursor, now)
          this.overview = false
        }
        break
    }
  }

  private step(command: ShowCommand, now: number): 'exit' | null {
    if (command === 'blank') {
      this.blank = !this.blank
      return null
    }
    if (command === 'confirm' && this.typed) {
      this.jump(now)
      return null
    }
    this.blank = false
    switch (command) {
      case 'next':
      case 'down':
      case 'confirm':
        return this.forward(now)
      case 'prev':
      case 'up':
        this.back(now)
        break
      case 'first':
        this.go(0, now)
        break
      case 'last':
        this.go(this.slides.length - 1, now)
        break
    }
    return null
  }

  private forward(now: number): 'exit' | null {
    if (this.ended) return 'exit'
    if (this.index < this.slides.length - 1) this.go(this.index + 1, now)
    else {
      this.settle(now)
      this.ended = true
    }
    return null
  }

  private back(now: number): void {
    if (this.ended) {
      this.ended = false
      this.enteredAt = now
    } else if (this.index > 0) this.go(this.index - 1, now)
  }

  /** Show slide `index` (by place). */
  go(index: number, now: number): void {
    const place = Math.min(Math.max(index, 0), this.slides.length - 1)
    if (!this.ended) this.settle(now)
    else this.enteredAt = now
    this.ended = false
    this.blank = false
    this.index = place
    this.cursor = place
  }

  /** Put what has been spent on the slide that is shown into the books, and start counting afresh. */
  private settle(now: number): void {
    this.spent[this.current.id] = (this.spent[this.current.id] ?? 0) + Math.max(0, now - this.enteredAt)
    this.enteredAt = now
  }

  // ------------------------------------------------------------------------------ the clock
  /** Seconds since the show started; the clock runs on in a blank screen, the overview and the end. */
  elapsed(now: number): number {
    return Math.max(0, now - this.startedAt)
  }

  /** Seconds on the slide that is shown, with those of earlier visits to it. */
  onSlide(now: number): number {
    const before = this.spent[this.current.id] ?? 0
    return this.ended ? before : before + Math.max(0, now - this.enteredAt)
  }

  /** How far the talk is from its plan: seconds behind (positive) or ahead (negative); null when no slide has a plan.
   * The plan is the time the slides before this one were given and what has gone of this one's; a slide that has no
   * plan counts as the time it took, so it is never late, and a slide that was skipped counts as time saved. */
  pace(now: number): number | null {
    if (this.planned.planned === 0) return null
    let scheduled = 0
    for (let i = 0; i < this.index; i++) {
      const slide = this.slides[i]!
      scheduled += slide.seconds ?? this.spent[slide.id] ?? 0
    }
    const here = this.onSlide(now)
    scheduled += this.slidePlan === null ? here : Math.min(here, this.slidePlan)
    return this.elapsed(now) - scheduled
  }
}
