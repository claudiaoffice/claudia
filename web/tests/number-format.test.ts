// The grid's number formats (lib/number-format.ts) against the cases the server's renderer is checked against
// (packages/claudia-computes/tests/number_format_cases.json): the two must agree on every line (D378).
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { ENGLISH, GERMAN, kindOf, render, rounded, splitSections, symbolsFor } from '~/lib/number-format'

interface Case {
  code: string
  value: number | string | boolean
  locale: 'en' | 'de'
  shows: string
}
const cases: Case[] = JSON.parse(
  readFileSync(join(__dirname, '..', '..', 'packages', 'claudia-computes', 'tests', 'number_format_cases.json'), 'utf8'),
).cases
const SYMBOLS = { en: ENGLISH, de: GERMAN }

describe('a value seen through a format code', () => {
  it.each(cases.map((c) => [`${c.code} | ${c.value} | ${c.locale}`, c] as const))('%s', (_, c) => {
    expect(render(c.value, c.code, SYMBOLS[c.locale]).text).toBe(c.shows)
  })

  it('says the colour a section asks for', () => {
    expect(render(-5, '#,##0;[Red]-#,##0').colour).toBe('red')
    expect(render(5, '#,##0;[Red]-#,##0').colour).toBeNull()
  })

  it('shows nothing for an empty cell', () => {
    expect(render(null, '0.00').text).toBe('')
  })
})

describe('reading a code', () => {
  it('splits sections only where the semicolon is not quoted or in brackets', () => {
    expect(splitSections('0;"a;b";[<0]0')).toEqual(['0', '"a;b"', '[<0]0'])
  })

  it('says what a code shows', () => {
    expect(kindOf('dd.mm.yyyy')).toBe('date')
    expect(kindOf('[h]:mm')).toBe('time')
    expect(kindOf('0.0%')).toBe('percent')
    expect(kindOf('General')).toBe('general')
    expect(kindOf('@')).toBe('text')
  })
})

describe('rounding as the server rounds', () => {
  it('rounds halves away from zero from the shortest text of the number', () => {
    expect(rounded(2.675, 2)).toBe('2.68')
    expect(rounded(0.5, 0)).toBe('1')
    expect(rounded(9.995, 2)).toBe('10.00')
    expect(rounded(1.5e-7, 3)).toBe('0.000')
    expect(rounded(1e21, 0)).toBe('1000000000000000000000')
  })
})

describe('the reader’s locale', () => {
  it('has tables for English and German and asks Intl for any other', () => {
    expect(symbolsFor('de-DE').decimal).toBe(',')
    expect(symbolsFor('de-CH').group).toBe('’')
    expect(symbolsFor('en-GB').shortDate).toBe('dd/mm/yyyy')
    expect(symbolsFor('fr-FR').decimal).toBe(',')
    expect(symbolsFor('fr-FR').months[10]).toBe('novembre')
  })
})
