import { describe, expect, it } from 'vitest'
import { Show, changesSince, showAction, type ShowSlide } from '~/lib/show'

const slides = (...seconds: (number | null)[]): ShowSlide[] => seconds.map((s, i) => ({ id: `s${i + 1}`, seconds: s, notes: i === 0 ? 'first' : '' }))
const key = (k: string, extra: object = {}) => ({ key: k, code: '', ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...extra })

describe('going through the slides', () => {
  it('starts where it is told to, on the slide and not on the overview', () => {
    const show = new Show(slides(60, 60, 60), { from: 1, now: 0 })
    expect(show.index).toBe(1)
    expect(show.current.id).toBe('s2')
    expect(show.next?.id).toBe('s3')
    expect(show.overview).toBe(false)
    expect(show.blank).toBe(false)
  })
  it('goes forward and back and stops at the first slide', () => {
    const show = new Show(slides(null, null, null), { from: 0, now: 0 })
    show.press('prev', 1)
    expect(show.index).toBe(0)
    show.press('next', 2)
    show.press('next', 3)
    expect(show.index).toBe(2)
    show.press('prev', 4)
    expect(show.index).toBe(1)
  })
  it('ends after the last slide, steps back from the end and leaves on the next press', () => {
    const show = new Show(slides(null, null), { from: 1, now: 0 })
    expect(show.press('next', 1)).toBeNull()
    expect(show.ended).toBe(true)
    expect(show.press('prev', 2)).toBeNull()
    expect(show.ended).toBe(false)
    expect(show.index).toBe(1)
    show.press('next', 3)
    expect(show.press('next', 4)).toBe('exit')
  })
  it('goes to the first and the last slide', () => {
    const show = new Show(slides(null, null, null, null), { from: 2, now: 0 })
    show.press('first', 1)
    expect(show.index).toBe(0)
    show.press('last', 2)
    expect(show.index).toBe(3)
    expect(show.ended).toBe(false)
  })
  it('blanks the screen and brings the slide back, and any move brings it back too', () => {
    const show = new Show(slides(null, null), { from: 0, now: 0 })
    show.press('blank', 1)
    expect(show.blank).toBe(true)
    show.press('blank', 2)
    expect(show.blank).toBe(false)
    show.press('blank', 3)
    show.press('next', 4)
    expect(show.blank).toBe(false)
    expect(show.index).toBe(1)
  })
  it('swaps between the audience view and the presenter view', () => {
    const show = new Show(slides(null), { from: 0, now: 0 })
    expect(show.view).toBe('audience')
    show.press('swap', 1)
    expect(show.view).toBe('presenter')
    show.press('swap', 2)
    expect(show.view).toBe('audience')
  })
  it('starts in the presenter view when asked to', () => {
    expect(new Show(slides(null), { from: 0, now: 0, view: 'presenter' }).view).toBe('presenter')
  })
  it('leaves on Esc', () => {
    expect(new Show(slides(null), { from: 0, now: 0 }).press('exit', 1)).toBe('exit')
  })
})

describe('the overview', () => {
  it('opens on the slide that is shown, moves a cell at a time and a row at a time', () => {
    const show = new Show(slides(...Array<null>(10).fill(null)), { from: 4, now: 0, columns: 4 })
    show.press('overview', 1)
    expect(show.overview).toBe(true)
    expect(show.cursor).toBe(4)
    show.press('next', 2)
    expect(show.cursor).toBe(5)
    show.press('down', 3)
    expect(show.cursor).toBe(9)
    show.press('down', 4)
    expect(show.cursor).toBe(9) // no slide below
    show.press('up', 5)
    expect(show.cursor).toBe(5)
    show.press('prev', 6)
    expect(show.cursor).toBe(4)
    expect(show.index).toBe(4) // looking is not going
  })
  it('goes to the slide on Enter and closes', () => {
    const show = new Show(slides(null, null, null), { from: 0, now: 0 })
    show.press('overview', 1)
    show.press('next', 2)
    show.press('next', 3)
    show.press('confirm', 4)
    expect(show.overview).toBe(false)
    expect(show.index).toBe(2)
  })
  it('closes on Esc without going anywhere, and a second Esc leaves', () => {
    const show = new Show(slides(null, null, null), { from: 0, now: 0 })
    show.press('overview', 1)
    show.press('next', 2)
    expect(show.press('exit', 3)).toBeNull()
    expect(show.overview).toBe(false)
    expect(show.index).toBe(0)
    expect(show.press('exit', 4)).toBe('exit')
  })
  it('closes when G is pressed again', () => {
    const show = new Show(slides(null, null), { from: 0, now: 0 })
    show.press('overview', 1)
    show.press('overview', 2)
    expect(show.overview).toBe(false)
  })
})

describe('jumping by number', () => {
  it('goes to the slide whose number was typed, on Enter', () => {
    const show = new Show(slides(...Array<null>(12).fill(null)), { from: 0, now: 0 })
    show.digit('1', 1)
    show.digit('0', 2)
    expect(show.typed).toBe('10')
    show.press('confirm', 3)
    expect(show.index).toBe(9)
    expect(show.typed).toBe('')
  })
  it('ignores a number there is no slide for, and clears what was typed', () => {
    const show = new Show(slides(null, null), { from: 0, now: 0 })
    show.digit('9', 1)
    show.press('confirm', 2)
    expect(show.index).toBe(0)
    expect(show.typed).toBe('')
  })
  it('lets Esc drop what was typed before it leaves', () => {
    const show = new Show(slides(null, null), { from: 0, now: 0 })
    show.digit('2', 1)
    expect(show.press('exit', 2)).toBeNull()
    expect(show.typed).toBe('')
    expect(show.press('exit', 3)).toBe('exit')
  })
  it('forgets digits that have been waiting for a while', () => {
    const show = new Show(slides(null, null, null), { from: 0, now: 0 })
    show.digit('3', 1)
    show.digit('1', 20)
    expect(show.typed).toBe('1')
  })
  it('goes to a slide in the overview by its number too', () => {
    const show = new Show(slides(null, null, null), { from: 0, now: 0 })
    show.press('overview', 1)
    show.digit('3', 2)
    show.press('confirm', 3)
    expect(show.index).toBe(2)
  })
})

describe('the clock of the talk (D343)', () => {
  it('counts the time since the start, and on this slide', () => {
    const show = new Show(slides(60, 120), { from: 0, now: 100 })
    expect(show.elapsed(130)).toBe(30)
    expect(show.onSlide(130)).toBe(30)
    show.press('next', 160)
    expect(show.elapsed(170)).toBe(70)
    expect(show.onSlide(170)).toBe(10)
  })
  it('adds up the time on a slide that is visited again', () => {
    const show = new Show(slides(60, 120), { from: 0, now: 0 })
    show.press('next', 40)
    show.press('prev', 50)
    expect(show.onSlide(70)).toBe(60) // 40 before, 20 now
  })
  it('knows the planned total and the plan of this slide', () => {
    const show = new Show(slides(60, null, 120), { from: 2, now: 0 })
    expect(show.planned).toEqual({ seconds: 180, planned: 2, unplanned: 1 })
    expect(show.slidePlan).toBe(120)
  })
  it('is on time when the time spent is the time planned', () => {
    const show = new Show(slides(60, 60, 60), { from: 0, now: 0 })
    show.press('next', 60)
    expect(show.pace(60)).toBe(0)
    expect(show.pace(90)).toBe(0) // half way through the next slide's time
  })
  it('is behind by what was spent over the plan, and ahead by what was saved', () => {
    const slow = new Show(slides(60, 60, 60), { from: 0, now: 0 })
    slow.press('next', 100)
    expect(slow.pace(100)).toBe(40)
    expect(slow.pace(100 + 70)).toBe(40 + 10) // past the plan of this slide too
    const quick = new Show(slides(60, 60, 60), { from: 0, now: 0 })
    quick.press('next', 30)
    expect(quick.pace(30)).toBe(-30)
  })
  it('counts the slides that were skipped as time saved', () => {
    const show = new Show(slides(60, 60, 60, 60), { from: 0, now: 0 })
    show.press('last', 30)
    expect(show.pace(30)).toBe(30 - 180)
  })
  it('does not call a slide without a plan late', () => {
    const show = new Show(slides(60, null, 60), { from: 0, now: 0 })
    show.press('next', 60)
    show.press('next', 600) // ten minutes on a slide nobody planned
    expect(show.pace(600)).toBe(0)
  })
  it('says nothing of pace when nothing is planned', () => {
    expect(new Show(slides(null, null), { from: 0, now: 0 }).pace(10)).toBeNull()
  })
  it('keeps counting while the screen is blank or the overview is open', () => {
    const show = new Show(slides(60), { from: 0, now: 0 })
    show.press('blank', 10)
    show.press('overview', 20)
    expect(show.elapsed(50)).toBe(50)
  })
})

describe('taking in what colleagues changed (D341)', () => {
  const list = (...ids: string[]): ShowSlide[] => ids.map((id) => ({ id, seconds: 60, notes: '' }))
  it('stays on the same slide when slides come in before it', () => {
    const show = new Show(list('s1', 's2', 's3'), { from: 1, now: 0 })
    show.update(list('s0', 's1', 's2', 's3'))
    expect(show.current.id).toBe('s2')
    expect(show.index).toBe(2)
  })
  it('stays near where it was when the slide it was on is gone', () => {
    const show = new Show(list('s1', 's2', 's3'), { from: 2, now: 0 })
    show.update(list('s1', 's2'))
    expect(show.current.id).toBe('s2')
  })
  it('keeps what was spent on the slides and the clock, and counts the new plan', () => {
    const show = new Show(list('s1', 's2'), { from: 0, now: 0 })
    show.press('next', 50)
    show.update([{ id: 's1', seconds: 100, notes: '' }, { id: 's2', seconds: 60, notes: 'new' }])
    expect(show.elapsed(80)).toBe(80)
    expect(show.planned.seconds).toBe(160)
    expect(show.pace(80)).toBe(50 - 100)
    expect(show.current.notes).toBe('new')
  })
  it('closes the overview and the end screen only as far as it must', () => {
    const show = new Show(list('s1', 's2'), { from: 1, now: 0 })
    show.press('next', 5)
    expect(show.ended).toBe(true)
    show.update(list('s1', 's2', 's3'))
    expect(show.ended).toBe(false) // there is something to show after the last slide it knew
    expect(show.current.id).toBe('s3')
  })
})

describe('what changed while the show was running', () => {
  it('counts the steps since the show started, on one line', () => {
    expect(changesSince('main:12', 'main:15')).toBe(3)
    expect(changesSince('main:12', 'main:12')).toBe(0)
  })
  it('does not know it across lines, or without revisions', () => {
    expect(changesSince('main:12', 'draft:15')).toBeNull()
    expect(changesSince(null, 'main:1')).toBeNull()
    expect(changesSince('main:1', null)).toBeNull()
  })
  it('does not go below zero when somebody undid things', () => {
    expect(changesSince('main:12', 'main:9')).toBe(3)
  })
})

describe('the keys of the show', () => {
  it.each([
    ['ArrowRight', 'next'], ['ArrowDown', 'down'], ['PageDown', 'next'], [' ', 'next'], ['n', 'next'],
    ['ArrowLeft', 'prev'], ['ArrowUp', 'up'], ['PageUp', 'prev'], ['Backspace', 'prev'],
    ['Home', 'first'], ['End', 'last'],
    ['b', 'blank'], ['B', 'blank'], ['.', 'blank'],
    ['g', 'overview'], ['p', 'swap'],
    ['Escape', 'exit'], ['Enter', 'confirm'],
    ['f', 'fullscreen'],
  ])('reads %j as %s', (k, action) => {
    expect(showAction(key(k))).toBe(action)
  })
  it('lets a digit through as a digit', () => {
    expect(showAction(key('7'))).toEqual({ digit: '7' })
  })
  it('leaves a key with Ctrl, Alt or Meta to the browser', () => {
    expect(showAction(key('b', { ctrlKey: true }))).toBeNull()
    expect(showAction(key('ArrowRight', { altKey: true }))).toBeNull()
    expect(showAction(key('g', { metaKey: true }))).toBeNull()
  })
  it('ignores what it does not know', () => {
    expect(showAction(key('x'))).toBeNull()
  })
})
