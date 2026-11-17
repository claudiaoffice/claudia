// The words of an editable field as a paragraph holds them (step G): whatever the browser made of a line break — a
// "\n", a <br>, a <div> or <p> around the next line — it is one "\n". A paragraph has one look, so nothing else is kept,
// but its references (step H): each is drawn as an atom and read back as the U+FFFC it stands at.
import { FIELD_CHAR } from './references'

/** What is read of a node of the field: the DOM's own `Node` is one, and so is a plain object in a test. */
export interface WordNode {
  nodeType: number
  nodeName: string
  data?: string
  childNodes: ArrayLike<WordNode>
  /** an element's attribute: a reference is drawn as an element with `data-atom` (step H) */
  getAttribute?(name: string): string | null
}

const TEXT_NODE = 3
const BLOCKS = new Set(['DIV', 'P'])

const isAtom = (node: WordNode) => typeof node.getAttribute === 'function' && node.getAttribute('data-atom') !== null

/** The words in a field, its line breaks as "\n". */
export function editedWords(field: WordNode): string {
  let out = ''
  const walk = (node: WordNode, first: boolean) => {
    if (node.nodeType === TEXT_NODE) out += (node.data ?? '').split(FIELD_CHAR).join('') // typed words make no reference
    else if (isAtom(node)) out += FIELD_CHAR
    else if (node.nodeName === 'BR') out += '\n'
    else {
      // a block the browser wrapped a new line in starts on a line of its own
      if (!first && BLOCKS.has(node.nodeName) && out && !out.endsWith('\n')) out += '\n'
      Array.from(node.childNodes).forEach((child) => walk(child, false))
    }
  }
  walk(field, true)
  return out.replace(/\n$/, '') // a line break at the very end is the browser's way to show an empty last line
}
