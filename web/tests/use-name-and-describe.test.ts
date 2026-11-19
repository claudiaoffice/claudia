// The state behind the Name & describe… dialog, the same for the three apps (D1317).
import { describe, expect, it, vi } from 'vitest'
import { useNameAndDescribe } from '~/lib/use-name-and-describe'
import type { ThingDetails } from '~/lib/name-and-describe'

const details: ThingDetails = { id: 'p1', kind: 'paragraph', name: 'Paragraph 1', name_fixed: false, description: '', drawn: false, decorative: false }
const host = () => ({
  thingDetails: vi.fn(async (_id: string): Promise<ThingDetails | false> => details),
  nameAndDescribe: vi.fn(async () => true),
  nameAndDescribeRange: vi.fn(async (): Promise<string | false> => 'r9'),
})
const form = { name: ' Intro ', description: ' Why ', decorative: false }

describe('useNameAndDescribe', () => {
  it('opens with what the server says about the thing, and saves name and words in one request', async () => {
    const session = host()
    const done = vi.fn()
    const dialog = useNameAndDescribe(session, done)
    await dialog.open('p1')
    expect(dialog.details.value).toEqual(details)
    await dialog.save(form)
    expect(session.nameAndDescribe).toHaveBeenCalledWith({ id: 'p1', name: 'Intro', description: 'Why', decorative: false })
    expect(dialog.details.value).toBeNull()
    expect(done).toHaveBeenCalledTimes(1)
  })
  it('does not open for a thing the server no longer knows', async () => {
    const session = host()
    session.thingDetails.mockResolvedValueOnce(false)
    const dialog = useNameAndDescribe(session, vi.fn())
    await dialog.open('gone')
    expect(dialog.details.value).toBeNull()
  })
  it('names cells that have no name through the range request, which has no id until it is saved', async () => {
    const session = host()
    const dialog = useNameAndDescribe(session, vi.fn())
    const region = { sheet: 's1', row0: 1, col0: 1, row1: 2, col1: 2 }
    dialog.openRange(region)
    expect(dialog.details.value).toMatchObject({ id: '', kind: 'range', name: '' })
    await dialog.save({ name: 'Costs', description: 'What we spend', decorative: false })
    expect(session.nameAndDescribeRange).toHaveBeenCalledWith(region, 'Costs', 'What we spend')
    expect(session.nameAndDescribe).not.toHaveBeenCalled()
  })
  it('closes without writing anything', async () => {
    const session = host()
    const done = vi.fn()
    const dialog = useNameAndDescribe(session, done)
    await dialog.open('p1')
    dialog.close()
    expect(dialog.details.value).toBeNull()
    expect(session.nameAndDescribe).not.toHaveBeenCalled()
    expect(done).toHaveBeenCalledTimes(1)
  })
})
