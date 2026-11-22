// Who answers @ai, in words (E7.11, D264): the badge of the panel and of the dialog, the line under an answer of the ai,
// and the muted line when the owners switch Claude on or off. Never by colour alone: a screen reader reads the same words.
import { translate as t } from './i18n'
import { currentLocale } from './locale'
import { clock } from './people'

/** Who answered, as the server puts it on a message of the ai and in `ai_consent` (`Via` of claudia_core). */
export interface Via {
  provider: string
  label: string
  remote: boolean
  /** A sentence that goes with it, in English: it is the key the catalogue translates. */
  note: string
}

/** One decision of the owners about Claude, as `ai_consent` lists them. */
export interface ConsentDecision {
  allowed: boolean
  who: string
  when: string
}

/** The owners' consent for Claude, and who answers here now (`ai_consent`). */
export interface ConsentView {
  provider: string
  allowed: boolean
  by: string | null
  at: string | null
  owners: string[]
  history: ConsentDecision[]
  answering: Via | null
  /** Does this server have Claude set up, so that there is something to allow? */
  offered: boolean
}

/** What the server says when it did not answer at all, or was stopped: they follow the badge in the same line. */
const OF_THE_LINE = ['no answer was made', 'stopped at its next step']

/** The badge: "Claude · remote" or "Qwen2.5-7B · this server". */
export function badge(via: Via): string {
  return `${via.label} · ${via.remote ? t('remote') : t('this server')}`
}

/** The line under a message of the ai: who gave the answer, or what became of the question. */
export function answeredBy(via: Via): string {
  if (OF_THE_LINE.includes(via.note)) return `${badge(via)} · ${t(via.note)}`
  return via.remote ? t('answered by {name} (remote)', { name: via.label }) : t('answered by {name}', { name: badge(via) })
}

/** The sentence about why this provider answered (Claude was not allowed here), apart from the line: `''` if none. */
export function noteOf(via: Via): string {
  return OF_THE_LINE.includes(via.note) || !via.note ? '' : t(via.note)
}

/** The muted line in the history when the owners decide about Claude: "jonas switched Claude off for this document." */
export function consentLine(decision: ConsentDecision): string {
  return decision.allowed
    ? t('{who} allowed Claude for this document.', { who: decision.who })
    : t('{who} switched Claude off for this document.', { who: decision.who })
}

/** What the dialog shows: the owners' checkbox, the state for everybody else, or that this server has no remote AI. */
export interface DialogModel {
  mode: 'owner' | 'read-only' | 'no-remote'
  /** For `read-only`: who can change it. */
  ownersLine: string
  /** Who decided last and when, for whom; empty while nobody has decided. */
  allowedLine: string
}

export function consentDialog(view: ConsentView, role: string): DialogModel {
  const mode = !view.offered ? 'no-remote' : role === 'owner' ? 'owner' : 'read-only'
  const owners = new Intl.ListFormat(currentLocale(), { style: 'long', type: 'conjunction' }).format(view.owners)
  const decided = view.by && view.at ? { who: view.by, time: clock(view.at) } : null
  const allowedLine = !decided
    ? ''
    : view.allowed
      ? t('Allowed by {who}, {time} · for Claude (Anthropic)', decided)
      : t('Switched off by {who}, {time} · for Claude (Anthropic)', decided)
  return { mode, ownersLine: t('Only the owners can change this: {owners}.', { owners }), allowedLine }
}
