import { describe, expect, it } from 'vitest'
import { DOT_EM, DOT_STEP_EM, LEADER_GAP_EM, leaderCss } from '../src/text/leader'

describe('the dot leader of a table of contents and of an agenda (CODE-60)', () => {
  it('is drawn on the screen with the gap, the dot and the step the printed pages use', () => {
    const css = leaderCss('dots')
    expect(css.margin).toBe(`0 ${LEADER_GAP_EM}em`)
    expect(css.height).toBe(`${DOT_EM}em`)
    expect(css.backgroundImage).toContain(`currentColor 0 ${DOT_EM}em`)
    expect(css.backgroundImage).toContain(`transparent ${DOT_EM}em ${DOT_STEP_EM}em`)
    expect(css.backgroundImage).toContain('to left') // counted from the page number, as the printed dots are
  })

  it('keeps the gaps and draws nothing for `none`', () => {
    expect(leaderCss('none')).toEqual({ flex: '1', margin: `0 ${LEADER_GAP_EM}em` })
  })

  it('takes the room between the words and the page', () => {
    expect(leaderCss('dots').flex).toBe('1')
  })
})
