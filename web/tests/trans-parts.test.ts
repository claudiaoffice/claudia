import { describe, expect, it } from 'vitest'
import { transParts } from '~/lib/trans-parts'

describe('transParts', () => {
  it('cuts a sentence at its placeholders, in the order the sentence has them', () => {
    expect(transParts('Hand {doc} over to {who}.')).toEqual([{ text: 'Hand ' }, { slot: 'doc' }, { text: ' over to ' }, { slot: 'who' }, { text: '.' }])
  })

  it('puts the placeholders where the translation has them, not where the English had them', () => {
    expect(transParts('Übergeben Sie {doc} an {who}.')).toEqual([{ text: 'Übergeben Sie ' }, { slot: 'doc' }, { text: ' an ' }, { slot: 'who' }, { text: '.' }])
    expect(transParts('{who} bekommt {doc}')).toEqual([{ slot: 'who' }, { text: ' bekommt ' }, { slot: 'doc' }])
  })

  it('leaves a sentence with no placeholder as one piece of text', () => {
    expect(transParts('Nothing to fill in')).toEqual([{ text: 'Nothing to fill in' }])
  })

  it('drops the empty pieces beside a placeholder at either end, and for no text at all', () => {
    expect(transParts('{a}{b}')).toEqual([{ slot: 'a' }, { slot: 'b' }])
    expect(transParts('')).toEqual([])
  })

  it('keeps a brace that is not a placeholder as text', () => {
    expect(transParts('{not a name} and {name}')).toEqual([{ text: '{not a name} and ' }, { slot: 'name' }])
  })
})
