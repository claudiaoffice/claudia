import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, ref } from 'vue'
import { useNoticeSaid } from '../app/lib/notice-said'
import type { Notice } from '../app/lib/base-session'

// A live region is only read when its text changes while it is already on the page (UX-88, BITV 4.1.3): the region is
// always there, and what it says is emptied first and filled a moment later.
describe('what a screen reader is told of a notice', () => {
  const notice = ref<Notice | null>(null)
  let said: ReturnType<typeof useNoticeSaid>

  beforeEach(() => {
    vi.useFakeTimers()
    notice.value = null
    said = useNoticeSaid(() => notice.value)
  })
  afterEach(() => vi.useRealTimers())

  async function settle() {
    await nextTick()
    vi.runAllTimers()
  }

  it('says nothing while there is no notice', () => {
    expect(said.value).toBe('')
  })

  it('says the text of a notice after it was empty', async () => {
    notice.value = { id: 1, kind: 'info', text: 'Checkpoint saved.' }
    await nextTick()
    expect(said.value).toBe('')
    vi.runAllTimers()
    expect(said.value).toBe('Checkpoint saved.')
  })

  it('empties itself and says a second notice with the same text again', async () => {
    notice.value = { id: 1, kind: 'warning', text: 'You can only look at this document.' }
    await settle()
    notice.value = { id: 2, kind: 'warning', text: 'You can only look at this document.' }
    await nextTick()
    expect(said.value).toBe('')
    vi.runAllTimers()
    expect(said.value).toBe('You can only look at this document.')
  })

  it('says nothing once the notice is gone', async () => {
    notice.value = { id: 1, kind: 'info', text: 'Checkpoint saved.' }
    await settle()
    notice.value = null
    await settle()
    expect(said.value).toBe('')
  })

  it('does not say a notice that went before its moment came', async () => {
    notice.value = { id: 1, kind: 'info', text: 'Checkpoint saved.' }
    await nextTick()
    notice.value = null
    await settle()
    expect(said.value).toBe('')
  })
})
