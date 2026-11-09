// E13.5's "in context" help for computes: while a formula is typed, the formula bar shows the signature and a
// short example of the function the caret is inside of — not autocomplete, and not every name that could still
// become a function (so `=SU` shows nothing yet; `=SUM(` does). `currentFunctionAt` finds that enclosing function
// purely from the text, with no knowledge of what functions exist; the caller (`functionHelp`, computes.py's
// `function_help`) is what says whether the name is real.

const NAME = /[A-Z][A-Z0-9_.]*$/i

/** The name of the function whose argument list the caret is inside of, or `null` if the caret is not inside any
 * function's parentheses (or is inside a string literal — a `)` or `(` quoted as text does not count). */
export function currentFunctionAt(text: string, caret: number): string | null {
  let depth = 0
  for (let i = Math.min(caret, text.length) - 1; i >= 0; i--) {
    const ch = text[i]
    if (ch === '"') {
      i = text.lastIndexOf('"', i - 1) // jump to before the literal's opening quote (a rough skip: an escaped
      if (i < 0) return null //  quote inside the literal is not handled — formulas rarely need one)
    } else if (ch === ')') {
      depth++
    } else if (ch === '(') {
      if (depth === 0) {
        const match = NAME.exec(text.slice(0, i))
        return match ? match[0].toUpperCase() : null
      }
      depth--
    }
  }
  return null
}
