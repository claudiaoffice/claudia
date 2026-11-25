import { describe, expect, it } from 'vitest'
import { NAME_TAG_HEIGHT, nameTagInside } from '../app/lib/name-tag'
import { DEFAULT_ROW_HEIGHT } from '../app/lib/line-sizes'

describe("where a colleague's name tag goes on her box (UX-86)", () => {
  it('goes inside the top edge of a box in the first row, where the column letters would cover it', () => {
    expect(nameTagInside(0)).toBe(0)
  })

  it('goes inside while there is less room above the box than the tag needs', () => {
    expect(nameTagInside(NAME_TAG_HEIGHT - 1)).toBe(0)
  })

  it('goes above a box in the second row, as everywhere else', () => {
    expect(nameTagInside(DEFAULT_ROW_HEIGHT)).toBeNull()
    expect(nameTagInside(NAME_TAG_HEIGHT)).toBeNull()
  })

  it('stays at the top of the area for a box whose top is scrolled out of it', () => {
    expect(nameTagInside(-40)).toBe(40)
  })
})
