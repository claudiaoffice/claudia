// How `TransText.vue` cuts an already translated sentence: at its `{placeholder}`s, so each one can be replaced by
// a slot (bold text, a link, a code sample) wherever the target language puts it. Kept out of the component so it
// is tested without mounting anything.

/** One piece of a sentence: plain text, or the name of the placeholder that a slot fills. */
export type TransPart = { text: string } | { slot: string }

/**
 * `text` cut at its `{name}` placeholders, in order. Empty pieces are dropped, so a sentence that starts or ends
 * with a placeholder has no empty text part beside it. A brace that is not a placeholder (`{not a name}`) stays text.
 */
export function transParts(text: string): TransPart[] {
  const parts: TransPart[] = []
  for (const piece of text.split(/(\{\w+\})/)) {
    if (piece === '') continue
    const slot = /^\{(\w+)\}$/.exec(piece)?.[1]
    parts.push(slot === undefined ? { text: piece } : { slot })
  }
  return parts
}
