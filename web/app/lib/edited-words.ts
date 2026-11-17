// The words of an editable field as a paragraph holds them (step G): whatever the browser made of a line break — a
// "\n", a <br>, a <div> or <p> around the next line — it is one "\n". A paragraph has one look, so nothing else is kept.

/** What is read of a node of the field: the DOM's own `Node` is one, and so is a plain object in a test. */
export interface WordNode {
  nodeType: number
  nodeName: string
  data?: string
  childNodes: ArrayLike<WordNode>
}

const TEXT_NODE = 3
const BLOCKS = new Set(['DIV', 'P'])

/** The words in a field, its line breaks as "\n". */
export function editedWords(field: WordNode): string {
  let out = ''
  const walk = (node: WordNode, first: boolean) => {
    if (node.nodeType === TEXT_NODE) out += node.data ?? ''
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
