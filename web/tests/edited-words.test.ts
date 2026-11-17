// The words of creates' paragraph editor (step G): line breaks as "\n", whatever the browser made of them.
import { describe, expect, it } from 'vitest'
import { editedWords, type WordNode } from '~/lib/edited-words'

const text = (data: string): WordNode => ({ nodeType: 3, nodeName: '#text', data, childNodes: [] })
const element = (nodeName: string, ...childNodes: WordNode[]): WordNode => ({ nodeType: 1, nodeName, childNodes })

describe('the words of an edited paragraph', () => {
  it('reads text, <br> and the blocks a browser wraps new lines in as one paragraph with "\\n"', () => {
    expect(editedWords(element('SPAN', text('Why'), element('BR'), text('we')))).toBe('Why\nwe')
    expect(editedWords(element('SPAN', text('Why'), element('DIV', text('we')), element('DIV', element('BR'))))).toBe('Why\nwe\n')
    expect(editedWords(element('SPAN', text('one\ntwo')))).toBe('one\ntwo')
  })
  it('reads a reference as the U+FFFC it stands at, and a typed U+FFFC as nothing (step H)', () => {
    const atom: WordNode = { ...element('SPAN', text('2.1')), getAttribute: (name) => (name === 'data-atom' ? '' : null) }
    expect(editedWords(element('SPAN', text('see '), atom, text('.\ufffc')))).toBe('see \ufffc.')
  })
  it('drops the line break a browser keeps at the very end, and reads an empty field as no words', () => {
    expect(editedWords(element('SPAN', text('Why'), element('BR')))).toBe('Why')
    expect(editedWords(element('SPAN'))).toBe('')
  })
})
