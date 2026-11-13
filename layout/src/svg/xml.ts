/**
 * A small XML reader for SVG: elements, attributes and text, with namespaces resolved. It needs no DOM, so the
 * library reads an SVG the same way in a browser, in Node and on a server.
 *
 * It reads well-formed XML and refuses what an SVG for a document never needs and what could be abused: a DOCTYPE
 * (the only source of entity declarations), more than {@link XML_LIMITS} elements or nesting. Elements in the SVG
 * namespace (or in none) keep their local names; elements of other namespaces are kept with a `ns:` marker so they
 * can be skipped. Attributes in the XLink namespace lose their prefix (`xlink:href` becomes `href`).
 *
 * @module
 */

export const SVG_NS = 'http://www.w3.org/2000/svg'
const XLINK_NS = 'http://www.w3.org/1999/xlink'
const XML_NS = 'http://www.w3.org/XML/1998/namespace'

/** How much an SVG may hold. */
export const XML_LIMITS = { elements: 200_000, depth: 256 } as const

export interface XmlElement {
  /** the local name for an SVG element; `{namespace}name` for an element of another namespace */
  name: string
  attrs: Map<string, string>
  children: XmlNode[]
}
export type XmlNode = XmlElement | string

/** The text is not XML that can be read, or it is refused; the message says where and why. */
export class XmlError extends Error {}

const ENTITIES: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" }

function decode(text: string, at: number): string {
  if (!text.includes('&')) return text
  return text.replace(/&([^;&\s]*);?/g, (all, name: string) => {
    if (!all.endsWith(';')) throw new XmlError(`an & that does not start an entity, near ${at}`)
    if (name.startsWith('#x') || name.startsWith('#X')) return codePoint(parseInt(name.slice(2), 16), at)
    if (name.startsWith('#')) return codePoint(parseInt(name.slice(1), 10), at)
    const v = ENTITIES[name]
    if (v === undefined) throw new XmlError(`unknown entity &${name}; near ${at}`)
    return v
  })
}
function codePoint(n: number, at: number): string {
  if (!Number.isInteger(n) || n <= 0 || n > 0x10ffff || (n >= 0xd800 && n <= 0xdfff)) throw new XmlError(`a character reference that is no character, near ${at}`)
  return String.fromCodePoint(n)
}

const NAME = /[A-Za-z_:À-￿][\w.:\-·À-￿]*/y
const SPACE = /\s*/y

/** Read `text` as XML; the root element. */
export function parseXml(text: string): XmlElement {
  let i = 0
  let count = 0
  const n = text.length
  const fail = (what: string): never => {
    throw new XmlError(`${what} (at character ${i})`)
  }
  const skipSpace = () => {
    SPACE.lastIndex = i
    SPACE.exec(text)
    i = SPACE.lastIndex
  }
  const name = (): string => {
    NAME.lastIndex = i
    const m = NAME.exec(text)
    if (!m) fail('a name was expected')
    i = NAME.lastIndex
    return m![0]
  }
  if (text.charCodeAt(0) === 0xfeff) i = 1

  interface Open {
    el: XmlElement
    raw: string
    ns: Map<string, string>
  }
  const stack: Open[] = []
  let root: XmlElement | null = null
  const rootNs = new Map<string, string>([['xml', XML_NS]])

  const resolve = (raw: string, ns: Map<string, string>, attribute: boolean): string => {
    const colon = raw.indexOf(':')
    const prefix = colon < 0 ? '' : raw.slice(0, colon)
    const local = colon < 0 ? raw : raw.slice(colon + 1)
    if (attribute) {
      if (!prefix) return local
      const uri = ns.get(prefix)
      if (uri === XLINK_NS) return local
      if (uri === XML_NS) return `xml:${local}`
      return `{${uri ?? prefix}}${local}`
    }
    const uri = ns.get(prefix) ?? (prefix ? undefined : '')
    if (uri === undefined) fail(`the prefix ${prefix} is not declared`)
    return uri === SVG_NS || uri === '' ? local : `{${uri}}${local}`
  }

  while (i < n) {
    const lt = text.indexOf('<', i)
    if (lt < 0) {
      if (text.slice(i).trim() && !stack.length) fail('text outside the root element')
      if (stack.length) fail('the document ends inside an element')
      break
    }
    if (lt > i) {
      const t = text.slice(i, lt)
      if (stack.length) stack.at(-1)!.el.children.push(decode(t, i))
      else if (t.trim()) fail('text outside the root element')
    }
    i = lt
    if (text.startsWith('<!--', i)) {
      const end = text.indexOf('-->', i + 4)
      if (end < 0) fail('a comment that does not end')
      i = end + 3
    } else if (text.startsWith('<![CDATA[', i)) {
      const end = text.indexOf(']]>', i + 9)
      if (end < 0) fail('a CDATA section that does not end')
      if (!stack.length) fail('CDATA outside the root element')
      stack.at(-1)!.el.children.push(text.slice(i + 9, end))
      i = end + 3
    } else if (text.startsWith('<?', i)) {
      const end = text.indexOf('?>', i + 2)
      if (end < 0) fail('a processing instruction that does not end')
      i = end + 2
    } else if (text.startsWith('<!', i)) {
      fail('a DOCTYPE or declaration is not allowed in an SVG here')
    } else if (text.startsWith('</', i)) {
      i += 2
      const raw = name()
      skipSpace()
      if (text[i] !== '>') fail('> expected')
      i++
      const open = stack.pop()
      if (!open || open.raw !== raw) fail(`</${raw}> does not close the open element`)
    } else {
      i++
      const raw = name()
      const rawAttrs: [string, string][] = []
      for (;;) {
        skipSpace()
        if (text[i] === '>' || text.startsWith('/>', i)) break
        const an = name()
        skipSpace()
        if (text[i] !== '=') fail('= expected after an attribute name')
        i++
        skipSpace()
        const q = text[i]
        if (q !== '"' && q !== "'") fail('an attribute value must be quoted')
        const end = text.indexOf(q!, i + 1)
        if (end < 0) fail('an attribute value that does not end')
        const value = text.slice(i + 1, end)
        if (value.includes('<')) fail('< in an attribute value')
        rawAttrs.push([an, decode(value, i)])
        i = end + 1
      }
      const selfClosing = text.startsWith('/>', i)
      i += selfClosing ? 2 : 1
      const parentNs = stack.length ? stack.at(-1)!.ns : rootNs
      let ns = parentNs
      for (const [an, v] of rawAttrs) {
        if (an === 'xmlns' || an.startsWith('xmlns:')) {
          if (ns === parentNs) ns = new Map(parentNs)
          ns.set(an === 'xmlns' ? '' : an.slice(6), v)
        }
      }
      const attrs = new Map<string, string>()
      for (const [an, v] of rawAttrs) {
        if (an === 'xmlns' || an.startsWith('xmlns:')) continue
        attrs.set(resolve(an, ns, true), v)
      }
      if (++count > XML_LIMITS.elements) fail(`more than ${XML_LIMITS.elements} elements`)
      if (stack.length >= XML_LIMITS.depth) fail(`elements nested more than ${XML_LIMITS.depth} deep`)
      const el: XmlElement = { name: resolve(raw, ns, false), attrs, children: [] }
      if (stack.length) stack.at(-1)!.el.children.push(el)
      else if (root) fail('a second root element')
      else root = el
      if (!selfClosing) stack.push({ el, raw, ns })
    }
  }
  if (stack.length) fail(`<${stack.at(-1)!.raw}> is not closed`)
  if (!root) fail('no root element')
  return root!
}

/** The text inside an element and its descendants, in order. */
export function textOf(el: XmlElement): string {
  let out = ''
  for (const c of el.children) out += typeof c === 'string' ? c : textOf(c)
  return out
}
