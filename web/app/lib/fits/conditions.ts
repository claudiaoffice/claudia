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
  { words: 'role: anyone', reason: 'role', holds: () => true, why: lookOnlyWords },
  {
    words: 'role: editor or owner',
    reason: 'role',
    holds: (f) => f.role !== 'viewer',
    why: lookOnlyWords,
  },
  { words: 'role: owner', reason: 'role', holds: (f) => f.role === 'owner', why: (t) => t('Only an owner can do this.') },
  ...(['LaTeX', 'Mermaid', 'Typst'] as const).map(
    (tool): Condition => ({
      words: `server: has the tool for ${tool}`,
      reason: 'server',
      holds: (f) => f.tools.has(tool.toLowerCase()),
      why: (t) => t('This server has no {tool} set up.', { tool }),
    }),
  ),
  {
    words: 'client: desktop only',
    reason: 'client',
    holds: (f) => f.client === 'desktop',
    why: (t) => t('This is only in the desktop app.'),
  },
  { words: 'ai: the ai can really answer', reason: 'ai', holds: (f) => f.ai, why: (t) => t('The ai is not set up on this server.') },
  {
    words: 'document: something to undo',
    reason: 'document',
    holds: (f) => f.document.undo,
    why: (t) => t('There is nothing to undo.'),
  },
  {
    words: 'document: something to redo',
    reason: 'document',
    holds: (f) => f.document.redo,
    why: (t) => t('There is nothing to redo.'),
  },
  {
    words: 'document: has something to refer to',
    reason: 'document',
    holds: (f) => f.document.references,
    why: (t) => t('There is nothing here to refer to yet.'),
  },
  {
    words: 'document: has random numbers',
    reason: 'document',
    holds: (f) => f.document.randomNumbers,
    why: (t) => t('There are no random numbers here.'),
  },
  {
    words: 'document: a place to go back to',
    reason: 'document',
    holds: (f) => f.document.backPlace,
    why: (t) => t('There is no place to go back to.'),
  },
  {
    words: 'document: has more than one slide',
    reason: 'document',
    holds: (f) => f.document.slides > 1,
    why: (t) => t('There is only one slide.'),
  },
  {
    words: 'selection: something',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind !== 'text' || x.range),
    why: (t) => t('Select something first.'),
  },
  {
    words: 'selection: text',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'text'),
    why: (t) => t('Put the cursor into a text first.'),
  },
  {
    words: 'selection: a list item',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'text' && x.listItem),
    why: (t) => t('Put the cursor into a list first.'),
  },
  {
    words: 'selection: a cell or range',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'cells'),
    why: (t) => t('Select a cell first.'),
  },
  {
    words: 'selection: more than one cell of the table',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'table-cells' && x.count > 1),
    why: (t) => t('Select more than one cell of the table first.'),
  },
  {
    words: 'selection: a merged cell',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'table-cells' && x.merged),
    why: (t) => t('Select a merged cell first.'),
  },
  {
    words: 'selection: an object that holds text',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'object' && x.holdsText),
    why: (t) => t('Select an object with words in it first.'),
  },
  {
    words: 'selection: an object that can turn',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'object' && x.canTurn),
    why: (t) => t('Select an object that can turn first.'),
  },
  {
    words: 'selection: an object on the grid',
    reason: 'selection',
    holds: (f) => each(f, (x) => x.kind === 'object' && x.onGrid),
    why: (t) => t('Select an object on the grid first.'),
  },
]

/** Every condition, by its words. */
export const CONDITIONS: ReadonlyMap<string, Condition> = new Map(LIST.map((c) => [c.words, c]))
