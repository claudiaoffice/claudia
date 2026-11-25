// The conditions a rule is made of (D1601, D1615), each in the workbook's words (D1646). A new condition is one entry
// here. Each says the sentence a notice shows when it does not hold (D1604, D1650); the `t('...')` calls are literal
// so that `scripts/extract_i18n.py` finds them.
import type { Facts, Reason, Thing } from './facts'

export type Translate = (msgid: string, vars?: Record<string, string | number>) => string

export interface Condition {
  /** As the workbook writes it: `role: editor or owner`. */
  words: string
  reason: Reason
  holds(facts: Facts): boolean
  /** The sentence of a notice, or of an empty menu's line, when it does not hold. */
  why(t: Translate): string
  /** When it holds, in plain words for Preferences ▸ Shortcuts (D1604): "owners", "when something is selected". */
  plain(t: Translate): string
}

/** What someone who may only look is told (CODE-98, D1650): written here once, said by the session too. */
export function lookOnlyWords(t: Translate): string {
  return t('You can only look at this document.')
}

/** Each selected thing fits, and there is at least one. */
function each(facts: Facts, fits: (thing: Thing) => boolean): boolean {
  return facts.selection.length > 0 && facts.selection.every(fits)
}

const LIST: readonly Condition[] = [
  { words: 'role: anyone', reason: 'role', holds: () => true, why: lookOnlyWords, plain: (t) => t('everyone') },
  {
    words: 'role: editor or owner',
    reason: 'role',
    holds: (f) => f.role !== 'viewer',
    why: lookOnlyWords,
    plain: (t) => t('editors and owners'),
  },
  { words: 'role: owner', reason: 'role', holds: (f) => f.role === 'owner', why: (t) => t('Only an owner can do this.'), plain: (t) => t('owners') },
  ...(['LaTeX', 'Mermaid', 'Typst'] as const).map(
    (tool): Condition => ({
      words: `server: has the tool for ${tool}`,
      reason: 'server',
      holds: (f) => f.tools.has(tool.toLowerCase()),
      why: (t) => t('This server has no {tool} set up.', { tool }),
      plain: (t) => t('when the server has {tool}', { tool }),
    }),
  ),
  {
    words: 'client: desktop only',
    reason: 'client',
    holds: (f) => f.client === 'desktop',
    why: (t) => t('This is only in the desktop app.'),
    plain: (t) => t('in the desktop app'),
  },
  { words: 'ai: the ai can really answer', reason: 'ai', holds: (f) => f.ai, why: (t) => t('The ai is not set up on this server.'), plain: (t) => t('when the ai can really answer') },
  {
    words: 'document: something to undo',
    reason: 'document',
    holds: (f) => f.document.undo,
    why: (t) => t('There is nothing to undo.'),
    plain: (t) => t('when there is something to undo'),
  },
  {
    words: 'document: something to redo',
    reason: 'document',
    holds: (f) => f.document.redo,
    why: (t) => t('There is nothing to redo.'),
    plain: (t) => t('when there is something to redo'),
  },
  {
    words: 'document: has something to refer to',
    reason: 'document',
    holds: (f) => f.document.references,
    why: (t) => t('There is nothing here to refer to yet.'),
    plain: (t) => t('when there is something to refer to'),
  },
  {
    words: 'document: has random numbers',
    reason: 'document',
    holds: (f) => f.document.randomNumbers,
    why: (t) => t('There are no random numbers here.'),
    plain: (t) => t('when there are random numbers'),
  },
  {
    words: 'document: a place to go back to',
    reason: 'document',
    holds: (f) => f.document.backPlace,
    why: (t) => t('There is no place to go back to.'),
    plain: (t) => t('when there is a place to go back to'),
  },
  {
    words: 'document: has more than one slide',
    reason: 'document',
    holds: (f) => f.document.slides > 1,
    why: (t) => t('There is only one slide.'),
    plain: (t) => t('when there is more than one slide'),
  },
  {
    words: 'selection: something',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind !== 'text' || x.range),
    why: (t) => t('Select something first.'),
    plain: (t) => t('when something is selected'),
  },
  {
    // what a style is for (D1654): something selected, or the paragraph the cursor is in
    words: 'selection: something, or the cursor in a text',
    reason: 'selection',
    holds: (f) => f.selection.length > 0,
    why: (t) => t('Select something first.'),
    plain: (t) => t('when something is selected or the cursor is in a text'),
  },
  {
    words: 'selection: text',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'text' || (x.kind === 'object' && x.holdsText)),
    why: (t) => t('Put the cursor into a text first.'),
    plain: (t) => t('when the cursor is in a text'),
  },
  {
    words: 'selection: a list item',
    reason: 'selection',
    holds: (f) => each(f, (x) => (x.kind === 'text' || (x.kind === 'object' && x.holdsText)) && !!x.listItem),
    why: (t) => t('Put the cursor into a list first.'),
    plain: (t) => t('when the cursor is in a list'),
  },
  {
    words: 'selection: a cell or range',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'cells'),
    why: (t) => t('Select a cell first.'),
    plain: (t) => t('when cells are selected'),
  },
  {
    words: 'selection: more than one cell of the table',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'table-cells' && x.count > 1),
    why: (t) => t('Select more than one cell of the table first.'),
    plain: (t) => t('when several boxes of a table are selected'),
  },
  {
    words: 'selection: a merged cell',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'table-cells' && x.merged),
    why: (t) => t('Select a merged cell first.'),
    plain: (t) => t('when a merged box of a table is selected'),
  },
  {
    words: 'selection: an object that holds text',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'object' && x.holdsText),
    why: (t) => t('Select an object with words in it first.'),
    plain: (t) => t('when an object with words is selected'),
  },
  {
    words: 'selection: an object that can turn',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'object' && x.canTurn),
    why: (t) => t('Select an object that can turn first.'),
    plain: (t) => t('when an object that can turn is selected'),
  },
  {
    words: 'selection: an object on the grid',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'object' && x.onGrid),
    why: (t) => t('Select an object on the grid first.'),
    plain: (t) => t('when an object on the grid is selected'),
  },
]

/** Every condition, by its words. */
export const CONDITIONS: ReadonlyMap<string, Condition> = new Map(LIST.map((c) => [c.words, c]))
