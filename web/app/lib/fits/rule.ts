// A rule is the workbook's "Fits when" text (D1646): conditions joined by "·", all of which must hold (D1601).
import { CONDITIONS, type Condition } from './conditions'

export type Rule = readonly Condition[]

const read = new Map<string, Rule>()

/** The conditions of ``words``; a phrase no condition has is a mistake in the definition, never a hidden entry. */
export function parseRule(words: string): Rule {
  const known = read.get(words)
  if (known) return known
  const phrases = words.split('·').map((phrase) => phrase.trim())
  const rule = phrases.map((phrase) => {
    const condition = CONDITIONS.get(phrase)
    if (!condition) throw new Error(`no condition "${phrase}" in the rule "${words}"`)
    return condition
  })
  read.set(words, rule)
  return rule
}
