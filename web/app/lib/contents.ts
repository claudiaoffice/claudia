// Tables of contents and agendas as every app's client knows them (E9.31; step E of
// claudiaoffice-log/notes/text-structure-across-apps.md). A table of contents is a generated paragraph: it stores only
// its options (`Toc`), and its entries are derived by the server from the headings (in creates: from the slide titles,
// which makes it an agenda). Nothing is ever updated by hand: an entry follows its heading for everybody at once. This
// module holds the shapes the server sends and what the options dialog and the drawing work out from them; the
// requests are the sessions' (`BaseSession.setContents` and the app's own insert).

/** The options of a table of contents (the server's `generated`): the heading levels it lists, whether it shows the
 * headings' numbers and their pages (in Page view, print and PDF; flow has no pages), and the leader to the page. */
export interface Toc {
  kind: 'toc'
  first: number
  last: number
  numbers: boolean
  places: boolean
  leader: Leader
}
export type Leader = 'dots' | 'none'
export const LEADERS: readonly Leader[] = ['dots', 'none']
/** The deepest heading level a table can list. */
export const MAX_LEVEL = 9

/** One line of a table (the server's `entries`): the paragraph it leads to, its level, the heading's number when it is
 * shown, its words and the style it is drawn in (`contents-<level>`); `place` is where the target is, when the server
 * knows (in creates: the slide number). */
export interface ContentsEntry {
  target: string
  level: number
  number: string | null
  text: string
  style: string
  place: string | null
}

/** What the options dialog works with: the table's options, what it lists and the session's requests. */
export interface ContentsHost {
  /** The table's paragraph (in composes a paragraph, in creates the agenda's text box). */
  paragraph: string
  options: Toc
  entries: readonly ContentsEntry[]
  /** The names of the styles a table is drawn in, as the document calls them. */
  looks: readonly string[]
  readOnly: boolean
  set: (options: Toc) => Promise<boolean>
  remove: () => Promise<boolean>
}

/** The options with one field changed, kept in bounds: the levels stay between 1 and `MAX_LEVEL`, and moving one end
 * past the other moves the other along. */
export function withOption<K extends keyof Toc>(options: Toc, key: K, value: Toc[K]): Toc {
  const next = { ...options, [key]: value }
  next.first = clampLevel(next.first)
  next.last = clampLevel(next.last)
  if (next.first > next.last) {
    if (key === 'first') next.last = next.first
    else next.first = next.last
  }
  return next
}

const clampLevel = (level: number) => Math.min(MAX_LEVEL, Math.max(1, Math.round(Number.isFinite(level) ? level : 1)))

/** The words of an entry as a link reads them: the number, if shown, then the heading's words. */
export function entryWords(entry: ContentsEntry): string {
  return entry.number ? `${entry.number} ${entry.text}` : entry.text
}

/** What the table lists, counted: how many entries, and the levels they come from (for the dialog's "Shows" line). */
export function shows(entries: readonly ContentsEntry[]): { count: number; levels: number[] } {
  return { count: entries.length, levels: [...new Set(entries.map((e) => e.level))].sort((a, b) => a - b) }
}

/** The names of the styles a table's entries are drawn in, each once, in the order of their levels (the dialog's
 * "Looks"); the ids come from the server, so no client keeps a list of them. */
export function looksOf(entries: readonly ContentsEntry[], styles: readonly { id: string; name: string }[]): string[] {
  const ids = [...new Map([...entries].sort((a, b) => a.level - b.level).map((e) => [e.style, e])).keys()]
  return ids.map((id) => styles.find((s) => s.id === id)?.name ?? id)
}
