// The dot leader between an entry's words and its page (a table of contents) or place (an agenda): the numbers its
// drawing has in one place, for the printed pages and for the screen (CODE-60). The pages draw dots as small squares
// (`apps/composes.ts`, `apps/objects.ts`); the screen draws them with `leaderCss`, from the same numbers, so a table of
// contents does not look one way on the page being edited and another on paper.

/** The gap between an entry's words and its leader, and between the leader and the page, in em. */
export const LEADER_GAP_EM = 0.4
/** How far apart a leader's dots are, in em. */
export const DOT_STEP_EM = 0.5
/** How big one dot is, in em: a square on paper, a square on the screen. */
export const DOT_EM = 0.09

/** The kinds of leader: dots, or nothing but the gap. */
export type LeaderKind = 'dots' | 'none'

/**
 * The CSS of a leader on the screen: an empty flex item that takes the room between the words and the page. Its dots
 * sit on the baseline, flush with the page number and counted from there, as the printed ones are. ``none`` keeps the
 * gaps and draws nothing.
 */
export function leaderCss(kind: LeaderKind): Record<string, string> {
  const own: Record<string, string> = { flex: '1', margin: `0 ${LEADER_GAP_EM}em` }
  if (kind !== 'dots') return own
  return {
    ...own,
    height: `${DOT_EM}em`,
    backgroundImage: `repeating-linear-gradient(to left, currentColor 0 ${DOT_EM}em, transparent ${DOT_EM}em ${DOT_STEP_EM}em)`,
  }
}
