// A polite live region is on the page before its words come (UX-90, BITV 4.1.3): a screen reader may say nothing of a
// `role="status"` (or `aria-live="polite"`) element that appears together with its text, so no such element is made
// or shown by a condition; what it says is.
import { readdirSync, readFileSync } from 'node:fs'
import { parse } from 'vue/compiler-sfc'
import { describe, expect, it } from 'vitest'

interface Node {
  type: number
  tag?: string
  loc: { start: { line: number } }
  props?: { type: number, name: string, value?: { content: string } }[]
  children?: Node[]
  branches?: Node[]
}

const ELEMENT = 1
const ATTRIBUTE = 6
const CONDITIONS = new Set(['if', 'else-if', 'else', 'show'])

function isPolite(node: Node): boolean {
  return (node.props ?? []).some((prop) => prop.type === ATTRIBUTE
    && ((prop.name === 'role' && prop.value?.content === 'status')
      || (prop.name === 'aria-live' && prop.value?.content === 'polite')))
}

function isConditional(node: Node): boolean {
  return (node.props ?? []).some((prop) => prop.type !== ATTRIBUTE && CONDITIONS.has(prop.name))
}

function conditionalRegions(node: Node, found: number[] = []): number[] {
  if (node.type === ELEMENT && isPolite(node) && isConditional(node)) found.push(node.loc.start.line)
  for (const child of [...(node.children ?? []), ...(node.branches ?? [])]) conditionalRegions(child, found)
  return found
}

describe('polite live regions', () => {
  const app = new URL('../app/', import.meta.url)
  const components = readdirSync(app, { recursive: true, encoding: 'utf8' }).filter((path) => path.endsWith('.vue'))

  it('are on the page before what they say', () => {
    const conditional = components.flatMap((path) => {
      const template = parse(readFileSync(new URL(path, app), 'utf8')).descriptor.template
      return template ? conditionalRegions(template.ast as unknown as Node).map((line) => `${path}:${line}`) : []
    })
    expect(conditional).toEqual([])
  })

  it('are found when they are made by a condition', () => {
    const { descriptor } = parse('<template><div><p v-if="a > b" class="x"\n role="status">{{ a }}</p></div></template>')
    expect(conditionalRegions(descriptor.template!.ast as unknown as Node)).toEqual([1])
  })
})
