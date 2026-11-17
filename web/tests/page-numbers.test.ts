// Page view's page numbers for a table of contents (E9.31, step F): laid out like the print preview, only in Page view,
// only while a table shows pages, and once the typing has paused.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, reactive, ref } from 'vue'

const layOut = vi.fn()
vi.mock('~/lib/print/assets', () => ({ printAssets: async () => ({}) }))
vi.mock('~/lib/print/source', () => ({ textSource: () => ({ layOut }) }))

const { usePageNumbers } = await import('~/lib/print/page-numbers')

const TOC = { kind: 'toc', first: 1, last: 3, numbers: true, places: true, leader: 'dots' }
function session(places = true) {
  const state = reactive({ blocks: [{ id: 'toc', style: 'body', text: '', runs: [], generated: { ...TOC, places } }, { id: 'h1', style: 'heading-1', text: 'Why', runs: [] }], styles: [], page: null, language: 'de' })
  return { state } as any
}

beforeEach(() => {
  vi.useFakeTimers()
  layOut.mockReset()
  layOut.mockResolvedValue({ pageOf: new Map([['h1', 3]]) })
})
afterEach(() => vi.useRealTimers())

function mounted(s: any, on: () => boolean) {
  const scope = effectScope()
  const pages = scope.run(() => usePageNumbers(s, on, 100))!
  return { pages, scope }
}

describe('page numbers in Page view', () => {
  it('lays the text out once the typing has paused, and gives the page of each paragraph', async () => {
    const s = session()
    const { pages } = mounted(s, () => true)
    expect(layOut).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(150)
    expect(layOut).toHaveBeenCalledTimes(1)
    expect(pages.value?.get('h1')).toBe(3)
    s.state.blocks[1].text = 'Why we did it'
    await nextTick()
    await vi.advanceTimersByTimeAsync(50)
    s.state.blocks[1].text = 'Why we did it all'
    await nextTick()
    await vi.advanceTimersByTimeAsync(150)
    expect(layOut).toHaveBeenCalledTimes(2) // the two changes in a row are laid out once
  })

  it('does nothing in flow, nor for a table without pages, and forgets the pages when left', async () => {
    const view = ref<'flow' | 'page'>('flow')
    const { pages } = mounted(session(), () => view.value === 'page')
    await vi.advanceTimersByTimeAsync(150)
    expect(layOut).not.toHaveBeenCalled()
    view.value = 'page'
    await nextTick()
    await vi.advanceTimersByTimeAsync(150)
    expect(pages.value).not.toBeNull()
    view.value = 'flow'
    await nextTick()
    expect(pages.value).toBeNull()
    mounted(session(false), () => true)
    await vi.advanceTimersByTimeAsync(150)
    expect(layOut).toHaveBeenCalledTimes(1)
  })

  it('lays out for a page reference too (step I)', async () => {
    const s = session(false)
    s.state.blocks[1].shown = [{ text: '', state: 'page' }]
    const { pages } = mounted(s, () => true)
    await vi.advanceTimersByTimeAsync(150)
    expect(pages.value?.get('h1')).toBe(3)
  })

  it('shows no pages when the text cannot be laid out', async () => {
    layOut.mockRejectedValue(new Error('no fonts'))
    const { pages } = mounted(session(), () => true)
    await vi.advanceTimersByTimeAsync(150)
    expect(pages.value).toBeNull()
  })
})
