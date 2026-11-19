// The one Name & describe… dialog (D1317): what it checks before it sends, and what it sends.
import { describe, expect, it } from 'vitest'
import { MAX_THING_NAME, checkNameAndDescribe, nameAndDescribeParams, unnamedRangeDetails, type ThingDetails } from '~/lib/name-and-describe'

const thing = (over: Partial<ThingDetails> = {}): ThingDetails => ({
  id: 'p1',
  kind: 'paragraph',
  name: 'Paragraph 1',
  name_fixed: false,
  description: '',
  drawn: false,
  decorative: false,
  ...over,
})
const form = (over: Partial<{ name: string; description: string; decorative: boolean }> = {}) => ({ name: 'Paragraph 1', description: '', decorative: false, ...over })

describe('checkNameAndDescribe', () => {
  it('has nothing to say about a name and words that are fine', () => {
    expect(checkNameAndDescribe(thing(), form({ name: 'Intro', description: 'Why we write' }))).toEqual({ name: null, description: null })
  })
  it('lets a thing that has no name stay without one, but not lose the one it has', () => {
    expect(checkNameAndDescribe(thing({ name: '' }), form({ name: '' })).name).toBeNull()
    expect(checkNameAndDescribe(thing(), form({ name: '  ' })).name).toMatch(/some text/)
  })
  it('takes a name with spaces for a thing, and refuses a long one and control characters', () => {
    expect(checkNameAndDescribe(thing(), form({ name: 'Cost per head' })).name).toBeNull()
    expect(checkNameAndDescribe(thing(), form({ name: 'x'.repeat(MAX_THING_NAME + 1) })).name).toMatch(/at most 60/)
    expect(checkNameAndDescribe(thing(), form({ name: 'a\u0007b' })).name).toMatch(/control/)
  })
  it('does not check the name of a heading: it is shown locked and is its words', () => {
    expect(checkNameAndDescribe(thing({ kind: 'heading', name: 'Introduction', name_fixed: true }), form({ name: '' })).name).toBeNull()
  })
  it('asks a range that has no name yet for one, by the rules of a name in a formula', () => {
    const range = unnamedRangeDetails()
    expect(checkNameAndDescribe(range, form({ name: '' })).name).toMatch(/some text/)
    expect(checkNameAndDescribe(range, form({ name: 'Cost per head' })).name).toMatch(/starts with a letter/)
    expect(checkNameAndDescribe(range, form({ name: 'B2' })).name).toMatch(/is a cell/)
    expect(checkNameAndDescribe(range, form({ name: 'Costs' })).name).toBeNull()
  })
  it('needs words or the tick for a picture, and no words with the tick', () => {
    const picture = thing({ kind: 'image', drawn: true, name: 'Logo' })
    expect(checkNameAndDescribe(picture, form({ name: 'Logo' })).description).toMatch(/Describe the picture/)
    expect(checkNameAndDescribe(picture, form({ name: 'Logo', decorative: true })).description).toBeNull()
    expect(checkNameAndDescribe(thing({ kind: 'shape', drawn: true }), form()).description).toBeNull()
  })
  it('keeps a description short', () => {
    expect(checkNameAndDescribe(thing(), form({ description: 'x'.repeat(301) })).description).toMatch(/At most 300/)
  })
})

describe('nameAndDescribeParams', () => {
  it('sends the name and the words trimmed, and no words for a decoration', () => {
    expect(nameAndDescribeParams('p1', form({ name: ' Intro ', description: ' Why ' }))).toEqual({ id: 'p1', name: 'Intro', description: 'Why', decorative: false })
    expect(nameAndDescribeParams('o1', form({ name: 'Logo', description: 'old', decorative: true }))).toEqual({ id: 'o1', name: 'Logo', description: '', decorative: true })
  })
})

describe('unnamedRangeDetails', () => {
  it('is a thing with no id, no name and nothing drawn', () => {
    expect(unnamedRangeDetails()).toMatchObject({ id: '', kind: 'range', name: '', name_fixed: false, drawn: false })
  })
})
