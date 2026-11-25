// What is true now, for judging whether a menu entry fits (D1601): who you are, what the server, the client and the
// ai can do, what the document has, and what is selected. Plain data, gathered by the window and its workspace.

/** Why an entry does not fit, in the order a notice names them (D1642): who you are matters more than what is selected. */
export const REASONS = ['role', 'server', 'client', 'ai', 'document', 'selection'] as const
export type Reason = (typeof REASONS)[number]

/** One selected thing. A caret in text is a thing (`range: false`), so that text entries fit it, but not "something". */
export type Thing =
  | { kind: 'text'; range: boolean; listItem: boolean }
  | { kind: 'cells' }
  | { kind: 'table-cells'; count: number; merged: boolean }
  | { kind: 'object'; holdsText: boolean; canTurn: boolean; onGrid: boolean }

export interface Facts {
  role: 'owner' | 'editor' | 'viewer'
  client: 'web' | 'desktop'
  /** The ai can really answer: a model is set up, not the scripted stand-in (D1615). */
  ai: boolean
  /** The tools of the server that draw containers: `latex`, `mermaid`, `typst`. */
  tools: ReadonlySet<string>
  document: {
    undo: boolean
    redo: boolean
    /** Something a cross reference can point at. */
    references: boolean
    randomNumbers: boolean
    /** A place a tag in the chat took you from, to go back to (View ▸ Back Where I Was). */
    backPlace: boolean
    slides: number
  }
  /** Everything selected; several things fit only when each fits (D1601). */
  selection: readonly Thing[]
}
