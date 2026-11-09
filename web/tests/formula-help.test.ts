import { describe, expect, it } from 'vitest'
import { currentFunctionAt } from '~/lib/formula-help'

const at = (text: string) => currentFunctionAt(text, text.length)

describe('the function the caret is inside of', () => {
  it('is null before any function has been opened', () => {
    for (const text of ['', '=', '=S', '=SUM', '=A1+B1']) expect(at(text), text).toBeNull()
  })
  it('is the function right after its opening parenthesis', () => {
    expect(at('=SUM(')).toBe('SUM')
    expect(at('=sum(')).toBe('SUM') // case does not matter; functions are shown upper case
  })
  it('stays the enclosing function while typing an argument', () => {
    expect(at('=SUM(A1')).toBe('SUM')
    expect(at('=SUM(A1, 5')).toBe('SUM')
    expect(at('=ROUND(2.675, ')).toBe('ROUND')
  })
  it('is the innermost function when one call is nested in another', () => {
    expect(at('=SUM(ROUND(A1, ')).toBe('ROUND')
    expect(at('=ROUND(SUM(A1, A2), 0')).toBe('ROUND') // closed SUM(...) is behind us; ROUND is still open
  })
  it('is null once a call has been closed and the caret has moved past it', () => {
    expect(at('=SUM(A1, A2)')).toBeNull()
    expect(at('=SUM(A1)+')).toBeNull()
  })
  it('a function name with a dot is read whole', () => {
    expect(at('=VAR.P(')).toBe('VAR.P')
  })
  it('a parenthesis quoted inside a text does not count as one', () => {
    expect(at('=CONCAT("(", A1')).toBe('CONCAT')
  })
  it('works at any caret position, not only at the end of the text', () => {
    expect(currentFunctionAt('=SUM(A1, A2)', 8)).toBe('SUM')
    expect(currentFunctionAt('=SUM(A1, A2)', 0)).toBeNull()
  })
})
