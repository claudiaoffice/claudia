import { describe, expect, it } from 'vitest'
import type { ChatMessage, Entry } from '~/lib/base-session'
import {
  askOwnerNote,
  authorsReached,
  itemCount,
  mayRedact,
  mayRedactEntry,
  mayRedactMessage,
  nothingPicked,
  noteFor,
  partsWords,
  pickedCount,
  requestOf,
  spokenFiller,
  splitSteps,
  togglingEntry,
  togglingMessage,
  withParts,
  type RedactionPlan,
} from '~/lib/redaction'

const t = (msgid: string, vars: Record<string, string | number> = {}) => msgid.replace(/\{(\w+)\}/g, (_m, k) => String(vars[k]))
const step = (n: number, author: string | null = 'bob', extra: Partial<Entry> = {}): Entry => ({
  revision: `main:${n}`,
  author,
  origin: 'do',
  time: `2026-11-18T16:4${n}:00Z`,
  label: 'Set cell',
  summary: `D${n} = secret`,
  kind: 'computes.SetCells',
  redacted: false,
  ...extra,
})
const message = (number: number, author = 'bob', extra: Partial<ChatMessage> = {}): ChatMessage => ({
  number,
  author,
  to: '',
  text: 'the PIN is 4711',
  time: `2026-11-18T16:5${number}:00Z`,
  at: null,
  ...extra,
})
const plan = (extra: Partial<RedactionPlan> = {}): RedactionPlan => ({
  targets: ['main:1'],
  dependents: [],
  chat: [],
  imports: [],
  changes_now: true,
  allowed: true,
  others: [],
  steps: [step(1)],
  app: 'computes',
  ...extra,
})
const ana = { user: 'ana', role: 'owner' }
const bob = { user: 'bob', role: 'editor' }
const cy = { user: 'cy', role: 'viewer' }

describe('who may pick what (D727)', () => {
  it('lets owners and editors redact, viewers not', () => {
    expect([ana, bob, cy].map(mayRedact)).toEqual([true, true, false])
  })
  it('lets an owner pick any step with content, an editor only her own', () => {
    expect(mayRedactEntry(step(1, 'bob'), ana)).toBe(true)
    expect(mayRedactEntry(step(1, 'Bob'), bob)).toBe(true)
    expect(mayRedactEntry(step(1, 'ana'), bob)).toBe(false)
    expect(mayRedactEntry(step(1, 'ai'), bob)).toBe(false) // what the AI did for her is the AI's step
    expect(mayRedactEntry(step(1, 'bob'), cy)).toBe(false)
  })
  it('offers nothing for a record or a step that is redacted already', () => {
    expect(mayRedactEntry(step(1, 'ana', { kind: 'core.Checkpoint' }), ana)).toBe(false)
    expect(mayRedactEntry(step(1, 'ana', { kind: 'core.Redaction' }), ana)).toBe(false)
    expect(mayRedactEntry(step(1, 'ana', { redacted: true }), ana)).toBe(false)
  })
  it('lets an owner pick any message she sees, an editor only her own', () => {
    expect(mayRedactMessage(message(1, 'bob'), ana)).toBe(true)
    expect(mayRedactMessage(message(1, 'bob'), bob)).toBe(true)
    expect(mayRedactMessage(message(1, 'ana'), bob)).toBe(false)
    expect(mayRedactMessage(message(1, 'bob', { redacted: true }), ana)).toBe(false)
  })
})

describe('a pick', () => {
  it('takes steps and messages in and out again', () => {
    let picked = togglingEntry(nothingPicked(), 'main:2')
    picked = togglingMessage(picked, 3)
    expect(pickedCount(picked)).toBe(2)
    picked = togglingEntry(picked, 'main:2')
    expect(requestOf(picked)).toEqual({ revisions: [], chat: [3] })
  })
  it('keeps the parts of an import until the import itself goes out of the pick', () => {
    let picked = withParts(togglingEntry(nothingPicked(), 'main:1'), 'main:1', ['b2', 't1'])
    expect(requestOf(picked)).toEqual({ revisions: ['main:1'], chat: [], parts: { 'main:1': ['b2', 't1'] } })
    expect(requestOf(withParts(picked, 'main:1', null))).toEqual({ revisions: ['main:1'], chat: [] })
    picked = togglingEntry(picked, 'main:1')
    expect(picked.parts).toBeUndefined()
  })
})

describe('what the dialog says', () => {
  it('counts every step and message that goes, those that go along included', () => {
    expect(itemCount(plan({ steps: [step(1), step(2, 'ana')], dependents: ['main:2'], chat: [1] }))).toBe(3)
  })
  it('keeps the steps that go along apart', () => {
    const { picked, following } = splitSteps(plan({ steps: [step(1), step(2, 'ana')], dependents: ['main:2'] }))
    expect(picked.map((s) => s.revision)).toEqual(['main:1'])
    expect(following.map((s) => s.revision)).toEqual(['main:2'])
  })
  it('writes the note privately to one person and openly to several, never to herself (D728)', () => {
    const messages = [message(1, 'cy')]
    expect(authorsReached(plan({ steps: [step(1), step(2, 'ana')] }), messages, ana)).toEqual(['bob'])
    expect(noteFor(plan(), messages, ana, t)).toBe('@bob I redacted some of your work in the history of this document.')
    expect(noteFor(plan({ chat: [1] }), messages, ana, t)).toBe('bob, cy: I redacted some of your work in the history of this document.')
    expect(noteFor(plan({ steps: [step(1, 'ana')] }), messages, ana, t)).toBe('')
  })
  it('asks an owner by the times of the steps, never by their content (D727)', () => {
    const blocked = plan({ allowed: false, others: ['ana'], steps: [step(1), step(2, 'ana')], dependents: ['main:2'], chat: [1] })
    const note = askOwnerNote(blocked, [message(1)], t, (iso) => iso.slice(11, 16))
    expect(note).toBe('Could an owner please redact what I did at 16:41, 16:51? It also reaches work by ana.')
    expect(note).not.toContain('4711')
  })
  it('reads filler out as a count, not as blocks', () => {
    expect(spokenFiller('D8 = ██████ and █', t)).toBe('D8 = (redacted, length 6) and (redacted, length 1)')
  })
  it('names the parts an import is blanked in, by app (D728)', () => {
    expect(partsWords('composes', t)).toContain('paragraphs')
    expect(partsWords('computes', t)).toContain('cell ranges')
    expect(partsWords('creates', t)).toContain('slides')
  })
})
