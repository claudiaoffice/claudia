// What the entries and keys of a table in a text do (E9.32, D1208): rows and columns, Sort, Merge Cells, Split Cell and
// Table Options…, on the table the caret is in. Where they stand is the definition's (the table's context menu, its
// row and column headers'); whether one can be done now is `possible`. Plain functions over a small host, with no Vue
// and no DOM, so a test can check what is on, what is off and what a key does without mounting the page.

import { chordOf, type ShortcutDef } from './shortcuts'
import { gridOf, MAX_COLUMNS, MAX_ROWS, mergeRect, type TableInfo } from './tables'

type Translate = (msgid: string, vars?: Record<string, string | number>) => string

/** What Edit's table entries do. */
export type TableAction =
  | 'row-above'
  | 'row-below'
  | 'row-delete'
  | 'column-left'
  | 'column-right'
  | 'column-delete'
  | 'sort-ascending'
  | 'sort-descending'
  | 'merge-cells'
  | 'split-cell'
  | 'options'

/** The id of each action in the menu manifest (`manifest.py`), from which the keys come. */
export const TABLE_ACTION_IDS: Readonly<Record<TableAction, string>> = {
  'row-above': 'edit.row-insert-above',
  'row-below': 'edit.row-insert-below',
  'row-delete': 'edit.row-delete',
  'column-left': 'edit.column-insert-left',
  'column-right': 'edit.column-insert-right',
  'column-delete': 'edit.column-delete',
  'sort-ascending': 'tools.sort-ascending',
  'sort-descending': 'tools.sort-descending',
  'merge-cells': 'tools.merge-cells',
  'split-cell': 'tools.split-cell',
  options: 'tools.table-options',
}

/** What the entries need from the window: the table and the box the caret is in, and a way to do an action. */
export interface TableMenuHost {
  /** the table the caret is in, or `null` outside a table */
  table: TableInfo | null
  /** the box the caret is in */
  box: { row: string; col: string } | null
  readonly: boolean
  run: (action: TableAction) => void
}

/** Whether an action can be done now: the caret is in a box of a table, the person may edit, and the action has
 *  something to do (no row past 100, no last row or column deleted, nothing to merge). */
export function possible(h: Pick<TableMenuHost, 'table' | 'box' | 'readonly'>, action: TableAction): boolean {
  const { table, box } = h
  if (h.readonly || !table || !box) return false
  switch (action) {
    case 'row-above':
    case 'row-below':
      return table.rows.length < MAX_ROWS
    case 'column-left':
    case 'column-right':
      return table.columns.length < MAX_COLUMNS
    case 'row-delete':
      return table.rows.length > 1
    case 'column-delete':
      return table.columns.length > 1
    case 'merge-cells':
      return mergeRect(table, box) !== null
    case 'split-cell': {
      const grid = gridOf(table)
      return [...grid.header, ...grid.body].flat().some((b) => b.row === box.row && b.col === box.col && (b.rows > 1 || b.cols > 1))
    }
    default:
      return true
  }
}

/** The keys of those entries, which work in the box the caret is in: a box is a field of its own, and the window leaves
 *  a field its keys unless a shortcut says `whileTyping`. */
export function tableShortcuts(c: { t: Translate }, h: TableMenuHost): ShortcutDef[] {
  const { t } = c
  const labels: Readonly<Record<TableAction, () => string>> = {
    'row-above': () => t('Insert Row Above'),
    'row-below': () => t('Insert Row Below'),
    'row-delete': () => t('Delete Row'),
    'column-left': () => t('Insert Column Left'),
    'column-right': () => t('Insert Column Right'),
    'column-delete': () => t('Delete Column'),
    'sort-ascending': () => t('Sort Ascending'),
    'sort-descending': () => t('Sort Descending'),
    'merge-cells': () => t('Merge Cells'),
    'split-cell': () => t('Split Cell'),
    options: () => t('Table Options…'),
  }
  return (Object.keys(TABLE_ACTION_IDS) as TableAction[]).map((action) => ({
    id: TABLE_ACTION_IDS[action],
    get label() {
      return labels[action]()
    },
    chord: chordOf(TABLE_ACTION_IDS[action]),
    run: () => h.run(action),
    enabled: () => possible(h, action),
    whileTyping: true,
  }))
}
