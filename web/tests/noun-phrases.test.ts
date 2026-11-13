import { afterAll, describe, expect, it } from 'vitest'
import { useI18n } from '~/lib/i18n'
import { clearStyle, forThe, goToThis, markByPurpose, nounName, thisOnly, usesCount } from '~/lib/noun-phrases'

const NOUNS = ['paragraph', 'cell', 'text box', 'shape', 'picture', 'chart', 'object']

describe('noun phrases', () => {
  it('has one whole sentence per thing that is styled, so none is built from a noun', () => {
    expect(NOUNS.map(thisOnly)).toEqual([
      'This paragraph only',
      'This cell only',
      'This text box only',
      'This shape only',
      'This picture only',
      'This chart only',
      'This object only',
    ])
    expect(new Set(NOUNS.map((n) => goToThis(n))).size).toBe(NOUNS.length)
    expect(new Set(NOUNS.map((n) => markByPurpose(n, 'Style'))).size).toBe(NOUNS.length)
  })

  it('names a thing in lower case, and leaves a noun it does not know as it is', () => {
    expect(NOUNS.map(nounName)).toEqual(NOUNS)
    expect(nounName('sparkle')).toBe('sparkle')
  })

  it('falls back to the object sentence for a noun it does not know', () => {
    expect(thisOnly('sparkle')).toBe(thisOnly('object'))
    expect(goToThis('sparkle')).toBe(goToThis('object'))
    expect(markByPurpose('sparkle', 'Style')).toBe(markByPurpose('object', 'Style'))
    expect(usesCount('sparkle', 3)).toBe('3 objects')
  })

  it('puts the caption into the tooltip', () => {
    expect(markByPurpose('shape', 'Label')).toBe('Label: mark the shape by what it is for')
  })

  it('counts what uses a style, one and many apart', () => {
    expect(usesCount('paragraph', 1)).toBe('1 paragraph')
    expect(usesCount('paragraph', 4)).toBe('4 paragraphs')
    expect(usesCount('cell', 1)).toBe('1 cell')
    expect(usesCount('cell', 2)).toBe('2 cells')
    expect(usesCount('object', 1)).toBe('1 object')
    expect(usesCount('object', 5)).toBe('5 objects')
  })

  it('has the clear and heading sentences', () => {
    expect(clearStyle()).toBe('Clear cell style')
    expect(forThe()).toBe('For the cell')
  })

  describe('in German', () => {
    const i18n = useI18n()
    afterAll(() => i18n.choose('en'))

    it('reads each sentence from the catalog, so the German article and ending follow the noun', async () => {
      const catalog = {
        'This paragraph only': 'Nur dieser Absatz',
        'This cell only': 'Nur diese Zelle',
        '{count} cells': '{count} Zellen',
      }
      const real = globalThis.fetch
      globalThis.fetch = (async () => new Response(JSON.stringify(catalog), { status: 200 })) as typeof fetch
      try {
        await i18n.choose('de')
      } finally {
        globalThis.fetch = real
      }
      expect(thisOnly('paragraph')).toBe('Nur dieser Absatz')
      expect(thisOnly('cell')).toBe('Nur diese Zelle')
      expect(usesCount('cell', 2)).toBe('2 Zellen')
    })
  })
})
