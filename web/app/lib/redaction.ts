// Redaction in the clients (E3.14; D720–D728): who may pick what, what the dialog says, the note to the people whose
// work goes. Plain functions over the session's own data, no Vue and no DOM, so every rule has a test; the dialog
// (`RedactionDialog.vue`) and the panel (`SidePanel.vue`) only draw what these decide.

import type { ChatMessage, Entry } from './base-session'
import type { Region } from './protocol'

type Translate = (msgid: string, vars?: Record<string, string | number>) => string

/** The character a redacted character becomes (D720): one per character, so that every later place still holds. */
export const FILLER = '█'

/** The kind of the history's record of a redaction. */
export const REDACTION_KIND = 'core.Redaction'

/** Records of the history that hold no content, so there is nothing in them to redact (D720). */
const RECORDS: ReadonlySet<string> = new Set(['core.Checkpoint', 'core.Redaction', 'core.Restore', 'core.Switch'])

/** Who the person is in this document. */
export interface Me {
  user: string
  role: string
}

/** What `redaction_plan` answers (D721, D722, D727). */
export interface RedactionPlan {
  /** The steps asked for, and the later steps that stop working without them and go too. */
  targets: string[]
  dependents: string[]
  /** The chat messages, by number. */
  chat: number[]
  /** The targets that imported a file: its kept original goes too. */
  imports: string[]
  /** Does the document as people see it change? */
  changes_now: boolean
  /** May this person carry it out? An editor may not when it reaches somebody else's later step (`others`). */
  allowed: boolean
  others: string[]
  /** Every step that is blanked, as the history shows it. */
  steps: Entry[]
  app: string
  /** The token the views read the planned state with, and the places in it to mark (when allowed). */
  plan?: string
  regions?: Region[]
}

/** What the person picked: steps by revision, chat messages by number, and the parts of an import to blank. */
export interface Picked {
  revisions: string[]
  chat: number[]
  /** For an import: only these things (paragraphs, sheets or ranges, slides, objects), by id; absent for all of it. */
  parts?: Record<string, string[]>
}

export const nothingPicked = (): Picked => ({ revisions: [], chat: [] })

const same = (a: string | null | undefined, b: string) => (a ?? '').toLowerCase() === b.toLowerCase()

/** May this person redact anything at all here: owners and editors (D727). */
export function mayRedact(me: Me): boolean {
  return me.role === 'owner' || me.role === 'editor'
}

/** May this person pick this step (D727): an owner any step with content, an editor only her own. */
export function mayRedactEntry(entry: Entry, me: Me): boolean {
  if (!mayRedact(me) || entry.redacted || RECORDS.has(entry.kind ?? '')) return false
  return me.role === 'owner' || same(entry.author, me.user)
}

/** May this person pick this message (D727): an owner any message she can read (the panel shows only those), an
 * editor only her own. */
export function mayRedactMessage(message: ChatMessage, me: Me): boolean {
  if (!mayRedact(me) || message.redacted) return false
  return me.role === 'owner' || same(message.author, me.user)
}

/** How many things a pick holds. */
export function pickedCount(picked: Picked): number {
  return picked.revisions.length + picked.chat.length
}

/** The pick with this step in it, or out of it again. */
export function togglingEntry(picked: Picked, revision: string): Picked {
  const has = picked.revisions.includes(revision)
  const revisions = has ? picked.revisions.filter((r) => r !== revision) : [...picked.revisions, revision]
  const parts = picked.parts && has ? withoutKey(picked.parts, revision) : picked.parts
  return { ...picked, revisions, ...(parts && Object.keys(parts).length ? { parts } : { parts: undefined }) }
}

/** The pick with this message in it, or out of it again. */
export function togglingMessage(picked: Picked, number: number): Picked {
  const chat = picked.chat.includes(number) ? picked.chat.filter((n) => n !== number) : [...picked.chat, number]
  return { ...picked, chat }
}

/** The pick with the parts of one import set (`null`: all of it). */
export function withParts(picked: Picked, revision: string, parts: string[] | null): Picked {
  const rest = withoutKey(picked.parts ?? {}, revision)
  const next = parts === null ? rest : { ...rest, [revision]: parts }
  return { ...picked, parts: Object.keys(next).length ? next : undefined }
}

function withoutKey(record: Record<string, string[]>, key: string): Record<string, string[]> {
  const { [key]: _gone, ...rest } = record
  return rest
}

/** The parameters `redaction_plan` and `redact` take for a pick. */
export function requestOf(picked: Picked): { revisions: string[]; chat: number[]; parts?: Record<string, string[]> } {
  return { revisions: [...picked.revisions], chat: [...picked.chat], ...(picked.parts ? { parts: picked.parts } : {}) }
}

/** How many items a plan blanks: every step, those that go with them included, and the messages. */
export function itemCount(plan: RedactionPlan): number {
  return plan.steps.length + plan.chat.length
}

/** The steps the person picked and the ones that go with them, apart. */
export function splitSteps(plan: RedactionPlan): { picked: Entry[]; following: Entry[] } {
  const following = new Set(plan.dependents)
  return {
    picked: plan.steps.filter((s) => !following.has(s.revision)),
    following: plan.steps.filter((s) => following.has(s.revision)),
  }
}

/** The people whose work a plan blanks, not counting the person herself, in order of first appearance. */
export function authorsReached(plan: RedactionPlan, messages: ChatMessage[], me: Me): string[] {
  const out: string[] = []
  const add = (who: string | null | undefined) => {
    if (who && !same(who, me.user) && !out.some((o) => same(o, who))) out.push(who)
  }
  for (const step of plan.steps) add(step.author)
  for (const number of plan.chat) add(messages.find((m) => m.number === number)?.author)
  return out
}

/** The chat note to the people whose work goes (D728): ticked by default, the person may change it. Private when it
 * is for one person (`@bob …`), for everybody when it is for several. Empty when only her own work goes. */
export function noteFor(plan: RedactionPlan, messages: ChatMessage[], me: Me, t: Translate): string {
  const who = authorsReached(plan, messages, me)
  if (!who.length) return ''
  if (who.length === 1) return t('@{name} I redacted some of your work in the history of this document.', { name: who[0]! })
  return t('{names}: I redacted some of your work in the history of this document.', { names: who.join(', ') })
}

/** The message an editor sends when her redaction reaches somebody else's work (D727): when, never what, so the
 * content does not land in the chat again. */
export function askOwnerNote(plan: RedactionPlan, messages: ChatMessage[], t: Translate, clock: (iso: string) => string): string {
  const { picked } = splitSteps(plan)
  const times = [
    ...picked.map((s) => clock(s.time)),
    ...plan.chat.map((n) => clock(messages.find((m) => m.number === n)?.time ?? '')),
  ].filter(Boolean)
  return t('Could an owner please redact what I did at {times}? It also reaches work by {names}.', {
    times: times.join(', '),
    names: plan.others.join(', '),
  })
}

/** What a screen reader says for a text with filler in it: each run as "redacted, length n", never the blocks. */
export function spokenFiller(text: string, t: Translate): string {
  return text.replace(/█+/g, (run) => ` ${t('(redacted, length {n})', { n: run.length })} `).replace(/\s+/g, ' ').trim()
}

/** The parts an import can be blanked in, by app (D723, D728): the words the dialog uses for them. */
export function partsWords(app: string, t: Translate): string {
  if (app === 'composes') return t('paragraphs, pictures and boxes')
  if (app === 'computes') return t('sheets, cell ranges, charts and objects')
  return t('slides and objects')
}
