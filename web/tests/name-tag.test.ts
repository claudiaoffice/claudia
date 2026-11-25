import { describe, expect, it } from 'vitest'
import { NAME_TAG_HEIGHT, nameTagPlace } from '../app/lib/name-tag'
import { DEFAULT_ROW_HEIGHT } from '../app/lib/line-sizes'

describe("where a colleague's name tag goes on her box (UX-86)", () => {
  it('goes inside the top edge of a box in the first row, where the column letters would cover it', () => {
    expect(nameTagPlace(0)).toBe('inside')
  })

  it('goes inside while there is less room above the box than the tag needs', () => {
    expect(nameTagPlace(NAME_TAG_HEIGHT - 1)).toBe('inside')
  })

  it('goes above a box in the second row, as everywhere else', () => {
    expect(nameTagPlace(DEFAULT_ROW_HEIGHT)).toBe('above')
    expect(nameTagPlace(NAME_TAG_HEIGHT)).toBe('above')
  })

  it('goes inside a box whose top is scrolled out of the area', () => {
    expect(nameTagPlace(-40)).toBe('inside')
  })
})
