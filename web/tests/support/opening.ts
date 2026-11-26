// What a server answers when a document is opened, for each app (E11.7): the requests of `BaseSession.reload` and of
// each session's `loadApp`, and what a session asks for the moment it is open (who is where, a lock). An empty
// document, as a new one is: a test that needs more says so with a handler, which wins over these.
//
// Only what the sessions need is answered. A request the session makes with a fallback for an older server (`.catch`:
// the tabs, the pivots, the number formats, the floating objects of a text, ...) is left out where the fallback is what
// an empty document wants, so the fallback is what runs, as it does in the tests that stand for such a server.
import type { Welcome } from '~/lib/protocol'
import { STYLE_MODEL } from '../style-model.fixture'

export type Answer = (params: any, welcome: Welcome) => unknown

const revisionOf = (w: Welcome) => w.revision ?? 'main:0'

/** The palette of a document that has none of its own roles yet. */
export const EMPTY_PALETTE = { type: 'palette', roles: [], readings: [] }

/** What every app answers (the kernel's methods). */
const all: Record<string, Answer> = {
  log: () => [],
  chat_log: () => [],
  checkpoints: () => [],
  history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
  branches: (_p, w) => w.branches,
  restore_policy: () => ({ policy: 'consensus' }),
  ping: (_p, w) => ({ revision: w.revision, branch: w.branch }),
  presence: () => ({}),
  lock: () => ({}),
  unlock: () => ({}),
  palette: () => EMPTY_PALETTE,
  style_model: () => STYLE_MODEL,
  styles: () => [],
  images: () => [],
}

const computes: Record<string, Answer> = {
  sheets: () => [{ id: 's1', name: 'Sheet1', rows: 0, cols: 0 }],
  objects: (p, w) => ({ revision: revisionOf(w), sheet: p.sheet, objects: [] }),
  cells: (_p, w) => ({ revision: revisionOf(w), cells: [] }),
  sizes: (_p, w) => ({ revision: revisionOf(w), rows: [], cols: [] }),
  diagrams: () => [],
  charts: () => [],
  names: (_p, w) => ({ revision: revisionOf(w), names: [] }),
}

const creates: Record<string, Answer> = {
  slides: () => [{ id: 's1', objects: 0 }],
  slide: (p, w) => ({ revision: revisionOf(w), slide: p.slide, objects: [] }),
  shapes: () => ({ library: [], document: [] }),
}

const composes: Record<string, Answer> = {
  paragraphs: () => ({ styles: [], paragraphs: [], lists: [], schemes: [] }),
  suggestions: () => [],
}

export const OPENING = { all, computes, composes, creates }
