// Whether an entry is offered, greyed or left out, and why (D1600, D1603, D1604, D1642, D1650): the rule against the
// facts, then the trial's policy for the reason of the first condition that fails.
import type { Translate } from './conditions'
import { REASONS, type Facts, type Reason } from './facts'
import type { FitPolicy } from './policy'
import type { Rule } from './rule'

export type Verdict =
  | { shown: true; enabled: true }
  | { shown: boolean; enabled: false; reason: Reason; why: string }

/** ``own``: an entry's own sentence for a reason, which a notice says instead of the condition's (D1650). */
export function judge(
  rule: Rule,
  facts: Facts,
  policy: FitPolicy,
  id: string,
  t: Translate,
  own: Partial<Record<Reason, string>> = {},
): Verdict {
  const failed = rule.filter((condition) => !condition.holds(facts))
  if (failed.length === 0) return { shown: true, enabled: true }
  const first = failed.reduce((a, b) => (REASONS.indexOf(b.reason) < REASONS.indexOf(a.reason) ? b : a))
  const display = policy.byEntry[id] ?? policy.byReason[first.reason]
  return { shown: display !== 'hide', enabled: false, reason: first.reason, why: own[first.reason] ?? first.why(t) }
}
