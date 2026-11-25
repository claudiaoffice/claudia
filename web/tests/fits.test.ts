// Whether a menu entry fits (D1600–D1606, D1642, D1650): its rule, read from the workbook's words (D1646), judged
// against what is true now. Plain data in, a verdict out: the seam agreed for slice 3 of the menu work.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { judge, type Verdict } from '~/lib/fits/judge'
import { DEFAULT_POLICY, policyFromAddress } from '~/lib/fits/policy'
import { parseRule } from '~/lib/fits/rule'
import type { Facts, Thing } from '~/lib/fits/facts'

const t = (msgid: string) => msgid

const caret: Thing = { kind: 'text', range: false, listItem: false }
const words: Thing = { kind: 'text', range: true, listItem: false }
const turning: Thing = { kind: 'object', holdsText: true, canTurn: true, onGrid: false }
const chart: Thing = { kind: 'object', holdsText: false, canTurn: false, onGrid: false }

function facts(over: Partial<Facts> = {}): Facts {
  return {
    role: 'owner',
    client: 'web',
    ai: true,
    tools: new Set(['latex', 'mermaid', 'typst']),
    document: { undo: false, redo: false, references: false, randomNumbers: false, backPlace: false, slides: 1 },
    selection: [],
    ...over,
  }
}

function verdict(rule: string, over: Partial<Facts> = {}, policy = DEFAULT_POLICY, id = 'edit.copy', own = {}): Verdict {
  return judge(parseRule(rule), facts(over), policy, id, t, own)
}

describe('a rule, in the workbook’s words (D1601, D1646)', () => {
  it('is its conditions joined by "·", each with its reason', () => {
    const rule = parseRule('role: editor or owner · selection: something')
    expect(rule.map((c) => [c.reason, c.words])).toEqual([
      ['role', 'role: editor or owner'],
      ['selection', 'selection: something'],
    ])
  })

  it('refuses words it does not know, rather than hiding an entry', () => {
    expect(() => parseRule('role: editor or owner · selection: a unicorn')).toThrow(/selection: a unicorn/)
    expect(() => parseRule('')).toThrow()
  })

  it('reads every rule of the definition, in every app and every place', () => {
    for (const app of ['composes', 'computes', 'creates']) {
      const listing = JSON.parse(readFileSync(resolve(__dirname, `../../clients/neutralino/src/generated/menu.${app}.json`), 'utf8'))
      const rules = new Set<string>()
      const walk = (node: unknown): void => {
        if (Array.isArray(node)) node.forEach(walk)
        else if (node && typeof node === 'object') {
          const entry = node as Record<string, unknown>
          if (typeof entry.fits === 'string') rules.add(entry.fits)
          Object.values(entry).forEach(walk)
        }
      }
      walk(listing)
      expect(rules.size).toBeGreaterThan(10)
      for (const rule of rules) expect(() => parseRule(rule), `${app}: ${rule}`).not.toThrow()
    }
  })
})

describe('judging an entry', () => {
  it('offers an entry whose conditions all hold', () => {
    expect(verdict('role: editor or owner · selection: something', { selection: [words] })).toEqual({ shown: true, enabled: true })
  })

  it('hides what does not fit by default, and says why (D1606, D1650)', () => {
    expect(verdict('role: owner', { role: 'viewer' })).toEqual({ shown: false, enabled: false, reason: 'role', why: 'Only an owner can do this.' })
  })

  it('greys instead when the trial sets the reason to grey', () => {
    const policy = policyFromAddress('?fits=role:grey')
    expect(verdict('role: owner', { role: 'editor' }, policy)).toMatchObject({ shown: true, enabled: false, reason: 'role' })
    expect(verdict('selection: something', {}, policy)).toMatchObject({ shown: false, reason: 'selection' })
  })

  it('lets an entry’s own setting beat its reason’s (D1606, D1653)', () => {
    const keep = policyFromAddress('?fits-entry=edit.undo:grey,edit.copy:hide&fits=document:hide,role:grey')
    expect(verdict('document: something to undo', {}, keep, 'edit.undo')).toMatchObject({ shown: true, enabled: false })
    expect(verdict('role: owner', { role: 'viewer' }, keep, 'edit.copy')).toMatchObject({ shown: false })
  })

  it('names who you are before what is selected (D1642)', () => {
    const v = verdict('role: editor or owner · selection: something', { role: 'viewer' })
    expect([v.reason, v.why]).toEqual(['role', 'You can only look at this document.'])
  })

  it('takes an entry’s own sentence for its reason, and the condition’s for the others (D1650)', () => {
    const own = { role: 'Only editors and owners can copy from this document.' }
    expect(verdict('role: editor or owner · selection: something', { role: 'viewer' }, DEFAULT_POLICY, 'edit.copy', own).why).toBe(own.role)
    expect(verdict('role: editor or owner · selection: something', {}, DEFAULT_POLICY, 'edit.copy', own).why).toBe('Select something first.')
  })

  it('needs every selected thing to fit (D1601)', () => {
    const rule = 'selection: an object that can turn'
    expect(verdict(rule, { selection: [turning] }).enabled).toBe(true)
    expect(verdict(rule, { selection: [turning, chart] }).enabled).toBe(false)
  })

  it('counts a caret in text as text, but not as something selected', () => {
    expect(verdict('selection: text', { selection: [caret] }).enabled).toBe(true)
    expect(verdict('selection: something', { selection: [caret] }).enabled).toBe(false)
    expect(verdict('selection: a list item', { selection: [{ ...caret, listItem: true }] }).enabled).toBe(true)
  })

  it('asks the server, the client and the ai what they can do', () => {
    expect(verdict('server: has the tool for LaTeX', { tools: new Set(['mermaid']) })).toMatchObject({ enabled: false, reason: 'server', why: 'This server has no {tool} set up.' })
    expect(verdict('client: desktop only', { client: 'web' })).toMatchObject({ enabled: false, reason: 'client' })
    expect(verdict('client: desktop only', { client: 'desktop' }).enabled).toBe(true)
    expect(verdict('ai: the ai can really answer', { ai: false })).toMatchObject({ enabled: false, reason: 'ai' })
  })

  it('reads the document: undo, redo, references, random numbers, a place to go back to, slides', () => {
    const doc = { undo: true, redo: false, references: true, randomNumbers: false, backPlace: true, slides: 2 }
    expect(verdict('document: something to undo', { document: doc }).enabled).toBe(true)
    expect(verdict('document: something to redo', { document: doc }).enabled).toBe(false)
    expect(verdict('document: has something to refer to · document: a place to go back to', { document: doc }).enabled).toBe(true)
    expect(verdict('document: has more than one slide', { document: { ...doc, slides: 1 } }).enabled).toBe(false)
  })
})

describe('the trial’s setting in the page’s address (D1606, D1647)', () => {
  it('starts every reason at hide, and ignores what it does not know', () => {
    expect(policyFromAddress('')).toEqual(DEFAULT_POLICY)
    expect(policyFromAddress('?fits-entry=edit.undo:show').byEntry).toEqual({}) // grey or hide only (D1653)
    expect(policyFromAddress('?fits=role:grey,nonsense:grey,ai:sideways')).toEqual({
      ...DEFAULT_POLICY,
      byReason: { ...DEFAULT_POLICY.byReason, role: 'grey' },
    })
  })
})
