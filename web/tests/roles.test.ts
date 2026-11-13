import { describe, expect, it } from 'vitest'
import {
  colourOf,
  contrast,
  flatten,
  luminance,
  nameOf,
  nearestRole,
  offPalette,
  readable,
  rgbOf,
  roleIn,
  roleValue,
  swatchFor,
  troubleWith,
  troubles,
} from '~/lib/roles'
import type { ColourRole, Reading } from '~/lib/objects'

const ROLES: ColourRole[] = [
  { id: 'text', name: 'Text', purpose: 'the words you read', colour: '#1F1A33' },
  { id: 'page', name: 'Page', purpose: 'the page itself', colour: '#F7F3EC' },
  { id: 'accent', name: 'Accent', purpose: 'the one thing to notice', colour: '#5B4BC4' },
  { id: 'accent-text', name: 'Accent text', purpose: 'words on the accent', colour: '#FFFFFF' },
]

const reading = (over: Partial<Reading> = {}): Reading => ({
  foreground: 'accent-text',
  background: 'accent',
  ratio: 1.42,
  floor: 4.5,
  ok: false,
  words: true,
  ...over,
})

describe('reading a value as a role', () => {
  it('finds the role and the opacity', () => {
    expect(roleIn('@accent')).toEqual({ role: 'accent', opacity: null })
    expect(roleIn('@accent/55')).toEqual({ role: 'accent', opacity: 55 })
    expect(roleIn('  @accent-text  ')).toEqual({ role: 'accent-text', opacity: null })
  })

  it('is not fooled by a literal, or by a token the server would refuse', () => {
    for (const value of ['#5B4BC4', 'rgb(1, 2, 3)', 'none', '', undefined, '@', '@UPPER', '@accent/0', '@accent/101'])
      expect(roleIn(value)).toBeNull()
  })

  it('writes the value back the way the server stores it', () => {
    expect(roleValue('accent')).toBe('@accent')
    expect(roleValue('accent', 55)).toBe('@accent/55')
    expect(roleValue('accent', 100)).toBe('@accent') // 100% is no opacity at all, so it is left off
  })
})

describe('what a person is shown', () => {
  it('names the role rather than its colour', () => {
    expect(nameOf('@accent', ROLES)).toBe('Accent')
    expect(nameOf('@accent/55', ROLES)).toBe('Accent at 55%')
    expect(nameOf('@gone', ROLES)).toBe('gone') // a role the palette no longer has still reads as itself
    expect(nameOf('#5B4BC4', ROLES)).toBe('#5B4BC4')
    expect(nameOf(undefined, ROLES)).toBe('None')
  })

  it('paints a swatch from the palette, and a wash as a mix so it reads true on any background', () => {
    expect(swatchFor('@accent', ROLES)).toBe('#5B4BC4')
    expect(swatchFor('@accent/14', ROLES)).toBe('color-mix(in srgb, #5B4BC4 14%, transparent)')
    expect(swatchFor('#ABCDEF', ROLES)).toBe('#ABCDEF')
    expect(swatchFor('@gone', ROLES)).toBe('transparent')
  })
})

describe('a colour off the palette', () => {
  it('is a deviation, which is allowed and only pointed out', () => {
    expect(offPalette('#F5D76E', ROLES)).toBe(true)
    expect(offPalette('@accent', ROLES)).toBe(false)
    expect(offPalette('@accent/14', ROLES)).toBe(false)
  })

  it('is not claimed for an empty value, or for a document with no palette at all', () => {
    expect(offPalette('', ROLES)).toBe(false)
    expect(offPalette('none', ROLES)).toBe(false)
    expect(offPalette('transparent', ROLES)).toBe(false)
    expect(offPalette('#F5D76E', [])).toBe(false)
  })

  it('offers the nearest role, which is the one click that adopts it', () => {
    expect(nearestRole('#5F50C8', ROLES)?.id).toBe('accent')
    expect(nearestRole('#FEFEFE', ROLES)?.id).toBe('accent-text')
    expect(nearestRole('#211A30', ROLES)?.id).toBe('text')
    expect(nearestRole('not a colour', ROLES)).toBeNull()
    expect(nearestRole('#5F50C8', [])).toBeNull()
  })
})

describe('contrast', () => {
  it('is the WCAG arithmetic', () => {
    expect(luminance('#000000')).toBeCloseTo(0)
    expect(luminance('#FFFFFF')).toBeCloseTo(1)
    expect(contrast('#000000', '#FFFFFF')).toBeCloseTo(21)
    expect(contrast('#5B4BC4', '#5B4BC4')).toBeCloseTo(1)
  })

  it('agrees with the server about the colours this suite uses', () => {
    // The same figures `claudia_core.contrast` gives, to four places: both sides have to agree, or a client would
    // warn about something the server thinks is fine.
    expect(contrast('#1F1A33', '#F7F3EC')).toBeCloseTo(15.1427, 3)
    expect(contrast('#FFFFFF', '#5B4BC4')).toBeCloseTo(6.4648, 3)
    expect(readable('#FFFFFF', '#5B4BC4')).toBe(true)
    expect(readable('#FFFFFF', '#F5D76E')).toBe(false)
  })

  it('reads a colour in either hex form', () => {
    expect(rgbOf('#5B4BC4')).toEqual([91, 75, 196])
    expect(rgbOf('#fff')).toEqual([255, 255, 255])
    expect(rgbOf('rgb(1, 2, 3)')).toBeNull()
  })
})

describe('what a failing reading is called', () => {
  it('says what it means for the person, and never the ratio (D202)', () => {
    const said = troubleWith(reading(), ROLES)
    expect(said).toBe('Accent text on Accent will be hard to read.')
    expect(said).not.toMatch(/1\.42|4\.5|:1/)
  })

  it('says something different about a border than about words', () => {
    expect(troubleWith(reading({ foreground: 'accent', background: 'page', words: false }), ROLES)).toBe(
      'Accent will be hard to make out against Page.',
    )
  })

  it('says nothing at all when the reading passes', () => {
    expect(troubleWith(reading({ ok: true, ratio: 6.46 }), ROLES)).toBeNull()
  })

  it('puts the worst trouble first and leaves out what passes', () => {
    const all = [reading({ ok: true, ratio: 9 }), reading({ ratio: 3.1 }), reading({ ratio: 1.42 })]
    expect(troubles(all).map((r) => r.ratio)).toEqual([1.42, 3.1])
  })
})

describe('a translucent colour', () => {
  it('is read with its opacity, not as the colour underneath it', () => {
    expect(colourOf('rgba(91, 75, 196, 0.14)')).toEqual([91, 75, 196, 0.14])
    expect(colourOf('rgb(91, 75, 196)')).toEqual([91, 75, 196, 1])
    expect(colourOf('#5B4BC4')).toEqual([91, 75, 196, 1])
    expect(colourOf('nonsense')).toBeNull()
  })

  it('flattens over what is behind it, which is what the eye actually sees', () => {
    // A shape's fill is `@accent/14`. Read as full-strength iris it looks far too dark to put words on; what is
    // really there is a pale wash a shade off the page, and the words on it are perfectly readable.
    const wash = flatten('rgba(91, 75, 196, 0.14)', '#F7F3EC')!
    expect(wash).toBe('#e1dbe6')
    expect(readable('#1F1A33', wash)).toBe(true)
    expect(readable('#1F1A33', '#5B4BC4')).toBe(false) // the false alarm this prevents
  })

  it('leaves an opaque colour exactly as it is, and falls back to white with nothing behind it', () => {
    expect(flatten('#5B4BC4', '#F7F3EC')).toBe('#5b4bc4')
    expect(flatten('rgba(0, 0, 0, 0.5)', undefined)).toBe('#808080')
    expect(flatten('nonsense', '#fff')).toBeNull()
  })
})
