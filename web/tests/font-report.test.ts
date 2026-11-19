// The font banner (E1.9, D1306): what it says about the fonts a document asks for that the server does not have, and
// to whom it offers "Get".
import { describe, expect, it } from 'vitest'
import { bannerSentence, mayOfferGet, type FontReport } from '~/lib/font-report'

const miss = (family: string, stand_in: string | null = 'Liberation Sans', closeness: 'same-widths' | 'other' = 'same-widths') => ({ family, stand_in, closeness })
const report = (...families: string[]): FontReport => ({ checked: true, missing: families.map((f) => miss(f)) })

describe('bannerSentence', () => {
  it('says nothing when nothing is missing, or when the server could not say', () => {
    expect(bannerSentence({ checked: true, missing: [] })).toBeNull()
    expect(bannerSentence({ checked: false, missing: [] })).toBeNull()
  })
  it('names one, two or three fonts, and counts the rest', () => {
    expect(bannerSentence(report('Calibri'))).toBe('This document uses a font this server does not have: Calibri. It is shown in a stand-in.')
    expect(bannerSentence(report('Calibri', 'Cambria'))).toBe('This document uses fonts this server does not have: Calibri, Cambria. They are shown in stand-ins.')
    expect(bannerSentence(report('A', 'B', 'C', 'D', 'E'))).toBe('This document uses fonts this server does not have: A, B, C and 2 more. They are shown in stand-ins.')
  })
})

describe('mayOfferGet', () => {
  it('is for an administrator only (the server refuses everybody else anyway)', () => {
    expect(mayOfferGet(true)).toBe(true)
    expect(mayOfferGet(false)).toBe(false)
  })
})
