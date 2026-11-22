// Containers, client side (D390–D396, D560): the definitions the server keeps, what it says of making
// their pictures, and the Markdown-like fences a text block can be turned into a container from.
import { pointer, type ObjectBody } from './objects'

/** One container's definition as the server sends it (`containers`, event `container`). */
export interface ContainerDef {
  format: number
  id: string
  type: string
  source: string
  params: Record<string, unknown>
  image: string | null
  renderer: string
  /** What the last try to draw it said, when a window joined after the try (`containers`); `null`: none yet. */
  outcome?: RenderOutcome | null
}

/** What a tool said about the text: how bad, what, and where (lines and columns from 1). */
export interface Diagnostic {
  severity: string
  message: string
  line: number | null
  column: number | null
}

/** The server's word on the last try to make a picture (event `render_result`). */
export interface RenderOutcome {
  ok: boolean
  diagnostics: Diagnostic[]
  message: string
  unavailable: string | null
}

/** One thing that can be made (`container_types`): the parts of it a client needs. */
export interface RenderType {
  type: string
  title: string
  example?: string
  ai_hint?: string
  max_source_chars?: number
  params?: unknown[]
  [more: string]: unknown
}

/** The server's word as a client keeps it: what an event `render_result` or a definition's `outcome` says. */
export function toOutcome(data: Partial<RenderOutcome>): RenderOutcome {
  return { ok: !!data.ok, diagnostics: data.diagnostics ?? [], message: data.message ?? '', unavailable: data.unavailable ?? null }
}

/** What the last tries said, by container, from the definitions the server sent: a window that joins after a try failed
 * must say "could not draw it" and not "drawing…" for ever. */
export function outcomesOf(definitions: readonly ContainerDef[]): Record<string, RenderOutcome> {
  const known: Record<string, RenderOutcome> = {}
  for (const definition of definitions) if (definition.outcome) known[definition.id] = toOutcome(definition.outcome)
  return known
}

export type RenderStatus =
  | { kind: 'empty' }
  | { kind: 'drawing' }
  | { kind: 'ready'; diagnostics: Diagnostic[] }
  | { kind: 'failed'; message: string; diagnostics: Diagnostic[] }
  | { kind: 'unavailable'; tool: string; message: string }

/** The id of the picture to show: the one the definition last made, if any. */
export function pictureOf(definition: ContainerDef | undefined): string | null {
  return definition?.image ?? null
}

/** What to tell about a container now: whether its text, its picture and the last outcome agree. */
export function renderStatus(definition: ContainerDef, outcome: RenderOutcome | undefined): RenderStatus {
  if (!definition.source.trim()) return { kind: 'empty' }
  if (outcome && !outcome.ok) {
    if (outcome.unavailable) return { kind: 'unavailable', tool: outcome.unavailable, message: outcome.message }
    return { kind: 'failed', message: outcome.message, diagnostics: outcome.diagnostics }
  }
  if (definition.image) return { kind: 'ready', diagnostics: outcome?.diagnostics ?? [] }
  return { kind: 'drawing' }
}

const OPEN = /^(`{3,})[ \t]*([A-Za-z][\w-]*)[ \t]*\n/

/** Text that is exactly one fenced block of a type that can be made, as `{type, source}`; else `null`. */
export function parseFence(text: string, types: readonly string[]): { type: string; source: string } | null {
  const open = OPEN.exec(text)
  if (!open) return null
  const fence = open[1]!
  const type = open[2]!.toLowerCase()
  if (!types.includes(type)) return null
  const rest = text.slice(open[0].length)
  const close = new RegExp(`(^|\\n)${fence}[ \\t]*$`)
  const found = close.exec(rest)
  if (!found) return null
  const source = rest.slice(0, found.index)
  if (new RegExp(`(^|\\n)${fence}`).test(source)) return null
  return { type, source }
}

/** A container's text as the fenced block it can be pasted as. */
export function formatFence(type: string, source: string): string {
  let ticks = '```'
  while (source.includes(ticks)) ticks += '`'
  return `${ticks}${type}\n${source}\n${ticks}`
}

export const fenceOf = (definition: ContainerDef): string => formatFence(definition.type, definition.source)

type Translate = (msgid: string, vars?: Record<string, string | number>) => string

/** What to say about a status beside or instead of the picture, and whether it is news the person must hear at once
 * (an alert) or only a state (a status). `label` is the type's name as people know it ("LaTeX"). */
export function statusText(status: RenderStatus, label: string, t: Translate): { text: string; urgent: boolean } {
  switch (status.kind) {
    case 'drawing':
      return { text: t('Drawing…'), urgent: false }
    case 'empty':
      return { text: t('Empty {type} container: double-click to write', { type: label }), urgent: false }
    case 'failed':
      return { text: t('Could not draw it: {message}', { message: status.message }), urgent: true }
    case 'unavailable':
      return { text: t('This server has no tool set up to draw {type}.', { type: label }), urgent: true }
    case 'ready':
      return { text: '', urgent: false }
  }
}

/** What the three apps' sessions hold of containers (`BaseState` plus the decoded pictures). */
export interface ContainerState {
  containers: Record<string, ContainerDef>
  renderOutcomes: Record<string, RenderOutcome>
  containerTypes: RenderType[]
  images: Record<string, { format: string; data: string }>
}

/** Everything a container's face needs: its definition, the picture's data URL (`''` before there is one), the type's
 * name, and the status. `null` for an object that shows no definition (yet). */
export function containerView(
  state: ContainerState,
  object: Pick<ObjectBody, 'kind' | 'ref'>,
  toUrl: (asset: { format: string; data: string }) => string,
): { definition: ContainerDef; src: string; label: string; status: RenderStatus } | null {
  const id = pointer(object, 'container')
  const definition = id ? state.containers[id] : undefined
  if (!definition) return null
  const picture = pictureOf(definition)
  const asset = picture ? state.images[picture] : undefined
  const label = state.containerTypes.find((k) => k.type === definition.type)?.title ?? definition.type
  // "Ready" means a picture the page can show: one that is named but has not arrived yet is still being drawn
  const status = renderStatus({ ...definition, image: asset ? picture : null }, state.renderOutcomes[definition.id])
  return { definition, src: asset ? toUrl(asset) : '', label, status }
}
