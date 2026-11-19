<script setup lang="ts">
// The text, drawn from the session's replica. The browser never changes it: every input is caught (`beforeinput`), turned
// into a request, and the text appears when the server's events arrive. What is typed but not yet sent is drawn at the
// caret as an overlay. Selections are translated between the page and the model (paragraph, offset).
import { computed, nextTick, onBeforeUnmount, onBeforeUpdate, onMounted, onUpdated, ref, shallowRef, watch } from 'vue'
import { leaderCss } from '@claudia/layout'
import { viewTints } from '~/lib/replay-tint'
import { colorOf } from '~/lib/people'
import type { Block, Pos } from '~/lib/blocks'
import { headingNumberLayout, itemLayout } from '~/lib/list-layout'
import { headingAttrs, paragraphCss, semanticTag } from '~/lib/style-css'
import type { TextSession } from '~/lib/text-session'
import { FIELD_CHAR, fieldIndex, partsOf, type Shown } from '~/lib/references'
import type { TextMark } from '~/lib/text-search-host'
import { useI18n } from '~/lib/i18n'
import { usePointed } from '~/lib/pointed'
import { columnOf, letsGoOfObject } from '~/lib/text-containers'
import { nearestBlock } from '~/lib/text-object-host'
import { wrapOf } from '~/lib/wrap'
import { floatStyle, measureFloats, takesRoom, type Hung, type WrapFloat, type WrapPage } from '~/lib/wrap-flow'
import { pointer } from '~/lib/objects'
import TableView from './TableView.vue'

const { t } = useI18n()

const props = defineProps<{
  session: TextSession
  view: 'flow' | 'page'
  authors: boolean
  active: string | null
  marks?: TextMark[]
  pages?: ReadonlyMap<string, number> | null
  /** A turn being tried from Rotate By… (nothing is sent until Done): the object is drawn at this angle meanwhile. */
  turning?: { id: string; turn: number } | null
}>()
const emit = defineEmits<{
  suggestion: [id: string]
  'style-menu': [at: { x: number; y: number }]
  contents: [block: string]
  'reference-menu': [at: { block: string; index: number; x: number; y: number }]
  'table-options': [table: string]
  /** The right button on a floating object or on a table: its menu opens there (D1225, D1224). */
  'object-menu': [at: { id: string; x: number; y: number }]
}>()

const state = props.session.state
/** What a replay marks (D553): a paragraph as a whole, whichever stretch of it changed. */
const tints = computed(() => viewTints(state))
const replayClass = (id: string) => {
  const tint = tints.value.block(id)
  return tint && `replay-${tint}`
}
const root = ref<HTMLElement | null>(null)
const scroller = ref<HTMLElement | null>(null)
const renderKey = ref(0)
let composing = false
// A paragraph is drawn from the CSS of its style (D73); the element only says what it is (a heading, a quote).
const tagOf = (style: string) => semanticTag(state.styles, style)
const headingOf = (style: string) => headingAttrs(state.styles, style)
// `resolved`, not `computed`: a palette role is a colour by the time it reaches the page (D200).
const cssOf = (style: string) => paragraphCss(state.styles.find((s) => s.id === style)?.resolved ?? {})

/** A list item's indent and gap, from the scheme of its list (E9.21), or a numbered heading's marker gap (E9.22); the
 * marker itself is drawn by CSS. */
const layoutOf = (at: number) => itemLayout(state.blocks, at, state.lists, state.schemes, cssOf(state.blocks[at]?.style ?? '')) ?? (state.blocks[at]?.label ? headingNumberLayout() : {})

// ------------------------------------------------------------------------------ what is drawn
interface TextSeg {
  kind: 'text'
  key: string
  start: number
  text: string
  author: string | null
  via: string | null
  sug: string | null
  remark: boolean
  zone: string | null
  zoneOwner: string | null
  /** What a search found here (E9.28): drawn with a band and an underline, and the one being looked at with an outline. */
  found: 'match' | 'current' | null
}
interface OtherSeg {
  kind: 'overlay' | 'caret' | 'reply'
  key: string
  text: string
  color?: string
  at?: number
  id?: string
}
/** A reference (step H): one character of the text, drawn as an atom that reads as what the server derived. */
interface FieldSeg {
  kind: 'field'
  key: string
  start: number
  index: number
  text: string
  state: Shown['state']
  target: string
}
type Seg = TextSeg | OtherSeg | FieldSeg

const clamp = (n: number, max: number) => Math.max(0, Math.min(n, max))

function segmentsOf(block: Block): Seg[] {
  const len = block.text.length
  const cuts = new Set([0, len])
  if (props.authors) {
    let at = 0
    for (const run of block.runs) cuts.add((at += run[0]))
  }
  const marks = state.suggestions.filter((s) => s.block === block.id)
  for (const s of marks) {
    cuts.add(clamp(s.start, len))
    cuts.add(clamp(s.end, len))
  }
  const hits = (props.marks ?? []).filter((m) => m.block === block.id)
  for (const h of hits) {
    cuts.add(clamp(h.start, len))
    cuts.add(clamp(h.end, len))
  }
  const zones: { user: string; start: number; end: number }[] = []
  const carets: { user: string; at: number }[] = []
  for (const [user, hold] of Object.entries(state.presence)) {
    for (const r of hold.regions) {
      if (r.kind !== 'text' || r.block !== block.id) continue
      const [start, end] = [clamp(r.start, len), clamp(r.end, len)]
      if (start < end) {
        zones.push({ user, start, end })
        cuts.add(start)
        cuts.add(end)
      } else {
        carets.push({ user, at: start })
        cuts.add(start)
      }
    }
  }
  const unwritten = [state.sending, state.pending].filter((u) => u && u.at.block === block.id)
  for (const u of unwritten) cuts.add(clamp(u!.at.offset, len))
  for (const part of partsOf(block.text)) {
    if (part.kind !== 'field') continue
    cuts.add(part.start)
    cuts.add(part.start + 1)
  }

  const points = [...cuts].sort((a, b) => a - b)
  const out: Seg[] = []
  const markers = (at: number) => {
    for (const s of marks) {
      if (s.replacement !== null && clamp(s.end, len) === at) out.push({ kind: 'reply', key: `r${s.id}`, text: s.replacement || '(delete)', id: s.id })
    }
    for (const c of carets) if (c.at === at) out.push({ kind: 'caret', key: `c${c.user}`, text: c.user, color: colorOf(state, c.user) })
    unwritten.forEach((u, i) => {
      if (clamp(u!.at.offset, len) === at) out.push({ kind: 'overlay', key: `o${i}`, text: u!.text, at })
    })
  }
  let run = 0
  let runEnd = block.runs[0]?.[0] ?? 0
  points.forEach((from, i) => {
    markers(from)
    const to = points[i + 1]
    if (to === undefined || to <= from) return
    while (run < block.runs.length && runEnd <= from) runEnd += block.runs[++run]?.[0] ?? Infinity
    const origin = block.runs[run]
    const sug = marks.find((s) => s.start <= from && s.end >= to && s.end > s.start)
    const zone = zones.find((z) => z.start <= from && z.end >= to)
    const hit = hits.find((h) => h.start <= from && h.end >= to && h.end > h.start)
    if (block.text[from] === FIELD_CHAR && to === from + 1) {
      const index = fieldIndex(block.text, from)
      const shown = block.shown?.[index]
      out.push({ kind: 'field', key: `f${from}`, start: from, index, text: shown?.text ?? '', state: shown?.state ?? 'ok', target: block.fields?.[index]?.target ?? '' })
      return
    }
    out.push({
      kind: 'text',
      key: `t${from}`,
      start: from,
      text: block.text.slice(from, to),
      author: origin?.[1] ?? null,
      via: origin?.[2] ?? null,
      sug: sug?.id ?? null,
      remark: sug ? sug.replacement === null : false,
      zone: zone ? colorOf(state, zone.user) : null,
      zoneOwner: zone?.user ?? null,
      found: hit ? (hit.current ? 'current' : 'match') : null,
    })
  })
  return out
}

const hasOverlay = (block: Block) => [state.sending, state.pending].some((u) => u && u.at.block === block.id)

function title(seg: TextSeg): string | undefined {
  if (seg.via) return t('{author}, from a suggestion of {via}', { author: seg.author ?? t('someone'), via: seg.via })
  if (props.authors && seg.author) return t('written by {author}', { author: seg.author })
  return seg.zoneOwner ? t('{author} is writing here', { author: seg.zoneOwner }) : undefined
}

// ------------------------------------------------------------------------------ page <-> model
const blockEl = (id: string) => root.value?.querySelector<HTMLElement>(`[data-block="${CSS.escape(id)}"]`) ?? null

/** How many characters of the text (not counting what only the screen shows) lie before a point of the page. A
 * reference is one character, whatever it reads as (step H). */
function textBefore(el: HTMLElement, node: Node, offset: number): number {
  const atom = (node.nodeType === Node.ELEMENT_NODE ? (node as HTMLElement) : node.parentElement)?.closest<HTMLElement>('[data-atom]')
  if (atom && el.contains(atom)) return Number(atom.dataset.off) + 1 // a point inside a reference is after it
  const range = document.createRange()
  range.selectNodeContents(el)
  range.setEnd(node, offset)
  let count = 0
  const walk = (n: Node) => {
    if (n.nodeType === Node.TEXT_NODE) count += (n as Text).data.length
    else if ((n as HTMLElement).hasAttribute?.('data-atom')) count += 1
    else if (!(n as HTMLElement).hasAttribute?.('data-skip')) n.childNodes.forEach(walk)
  }
  walk(range.cloneContents())
  return count
}

function posFromDom(node: Node, offset: number): Pos | null {
  const container = root.value
  if (!container || !container.contains(node)) return null
  if (node === container) {
    const blocks = state.blocks
    if (!blocks.length) return null
    const block = blocks[Math.min(offset, blocks.length - 1)]!
    return { block: block.id, offset: offset >= blocks.length ? block.text.length : 0 }
  }
  const el = (node.nodeType === Node.ELEMENT_NODE ? (node as HTMLElement) : node.parentElement)?.closest<HTMLElement>('[data-block]')
  if (!el?.dataset.block) return null
  const block = state.blocks.find((b) => b.id === el.dataset.block)
  if (!block) return null
  return { block: block.id, offset: Math.min(textBefore(el, node, offset), block.text.length) }
}

function domPoint(pos: Pos, afterOverlay: boolean): [Node, number] | null {
  const el = blockEl(pos.block)
  if (!el) return null
  if (afterOverlay) {
    const overlays = [...el.querySelectorAll<HTMLElement>('[data-overlay]')].filter((o) => Number(o.dataset.at) === pos.offset)
    const last = overlays.at(-1)
    if (last?.firstChild) return [last.firstChild, (last.firstChild as Text).data.length]
  }
  const atom = el.querySelector<HTMLElement>(`[data-atom][data-off="${pos.offset - 1}"]`)
  if (atom?.parentNode) return [atom.parentNode, [...atom.parentNode.childNodes].indexOf(atom) + 1] // right after a reference
  const segs = [...el.querySelectorAll<HTMLElement>('[data-seg]')]
  if (!segs.length) return [el, 0]
  const found = segs.find((s) => pos.offset < Number(s.dataset.off) + (s.textContent?.length ?? 0)) ?? segs.at(-1)!
  return [found.firstChild!, Math.max(0, Math.min(pos.offset - Number(found.dataset.off), (found.textContent ?? '').length))]
}

/** The tables that hang from a paragraph, in the order of their anchors (E9.32). */
function tablesAfter(block: string) {
  return props.session
    .objectsIn(block)
    .filter((o) => o.kind === 'table')
    .sort((a, b) => a.anchor.offset - b.anchor.offset)
    .flatMap((object) => {
      const id = pointer(object, 'table')
      const table = id ? state.tables[id] : undefined
      return table ? [{ object, table }] : []
    })
}

function placeSelection() {
  const container = root.value
  const sel = document.getSelection()
  const mine = state.selection
  if (!container || !sel || !mine || composing) return
  if (document.activeElement?.closest('[data-table]')) return // the caret is in a box of a table, not in the words
  if (document.activeElement !== container && !(sel.anchorNode && container.contains(sel.anchorNode))) return
  const same = mine.anchor.block === mine.focus.block && mine.anchor.offset === mine.focus.offset
  const a = domPoint(mine.anchor, false)
  const f = domPoint(mine.focus, same)
  if (!a || !f) return
  const there = sel.anchorNode === a[0] && sel.anchorOffset === a[1] && sel.focusNode === f[0] && sel.focusOffset === f[1]
  placed = key(mine.anchor, mine.focus)
  if (!there) sel.setBaseAndExtent(a[0], a[1], f[0], f[1])
  keepInView(f)
}

/** Scroll so that the caret is visible. */
function keepInView(point: [Node, number]) {
  const box = scroller.value
  if (!box) return
  const range = document.createRange()
  range.setStart(point[0], point[1])
  range.collapse(true)
  const rect = range.getClientRects()[0] ?? (point[0] as HTMLElement).getBoundingClientRect?.()
  if (!rect) return
  const view = box.getBoundingClientRect()
  if (rect.bottom > view.bottom - 24) box.scrollTop += rect.bottom - view.bottom + 48
  else if (rect.top < view.top + 24) box.scrollTop -= view.top - rect.top + 48
}

/** What we last put on the page: a page that still shows it has not been touched by the person since. */
let placed: string | null = null
const key = (a: Pos, f: Pos): string => `${a.block}:${a.offset}-${f.block}:${f.offset}`

/** Take the selection of the page as the person's. `always`: a click or key was seen; otherwise only if the page
 *  shows something other than what we put there (the model is ahead of the page for a moment after each change). */
function adoptSelection(always = false) {
  const now = domSelection()
  if (!now || (!always && key(...now) === placed)) return
  placed = key(...now)
  props.session.setSelection(...now)
}

function onSelectionChange() {
  if (!composing) adoptSelection(true)
}

/** The selection of the page as paragraph and offset, `null` if it is not in the text. */
function domSelection(): [Pos, Pos] | null {
  const sel = document.getSelection()
  if (!sel?.anchorNode || !sel.focusNode) return null
  const a = posFromDom(sel.anchorNode, sel.anchorOffset)
  const f = posFromDom(sel.focusNode, sel.focusOffset)
  return a && f ? [a, f] : null
}

// Drawing the text again can lose the caret (the nodes it sat in are replaced) and the page may not have told us yet
// that the person moved it. So: look before the redraw, take over what the person changed, draw, and put the caret back.
let before: [Pos, Pos] | null = null
onBeforeUpdate(() => {
  before = composing ? null : domSelection()
})

watch(
  () => [state.selection?.anchor.block, state.selection?.anchor.offset, state.selection?.focus.block, state.selection?.focus.offset],
  () => nextTick(placeSelection),
)
onUpdated(() => {
  if (before && key(...before) !== placed) props.session.setSelection(...before)
  before = null
  placeSelection()
})
// Where the paragraphs are on the page changes when the text wraps differently, so the containers hanging from them
// (D560) are placed again whenever the text's box changes size, and after a pause when the paragraphs change.
const layoutTick = ref(0)
let watcher: ResizeObserver | null = null
onMounted(() => {
  document.addEventListener('selectionchange', onSelectionChange)
  props.session.setAnchorProvider(firstVisibleBlock)
  if (typeof ResizeObserver === 'undefined') return
  watcher = new ResizeObserver(() => layoutTick.value++)
  if (root.value) watcher.observe(root.value)
  if (scroller.value) watcher.observe(scroller.value)
})
onBeforeUnmount(() => {
  document.removeEventListener('selectionchange', onSelectionChange)
  props.session.setAnchorProvider(null)
  watcher?.disconnect()
})
watch(
  () => Object.keys(state.objects).length + state.blocks.length,
  () => nextTick(() => layoutTick.value++),
)
watch(renderKey, () => nextTick(() => {
  if (root.value) watcher?.observe(root.value)
  layoutTick.value++
}))

// ------------------------------------------------------------------------------ input
/** Did the event start in a box of a table? Those are fields of their own (`TableView.vue`), not the words. */
const fromTable = (event: Event): boolean => !!(event.target as Element | null)?.closest?.('[data-table]')

function onBeforeInput(event: InputEvent) {
  props.session.clearBack() // the person went on from where a tag took them (D1312)
  if (fromTable(event)) return
  if (composing || event.isComposing) return // the input method is at work: compositionend tells us what came of it
  event.preventDefault()
  adoptSelection() // the page may have moved the caret before it told us
  const session = props.session
  switch (event.inputType) {
    case 'insertText':
    case 'insertReplacementText': {
      const range = event.getTargetRanges?.()[0]
      if (range && event.inputType === 'insertReplacementText') {
        const a = posFromDom(range.startContainer, range.startOffset)
        const f = posFromDom(range.endContainer, range.endOffset)
        if (a && f) session.setSelection(a, f)
      }
      const text = event.data ?? event.dataTransfer?.getData('text/plain') ?? ''
      if (text) session.type(text)
      break
    }
    case 'insertParagraph':
    case 'insertLineBreak':
      void session.newline()
      break
    case 'deleteContentBackward':
    case 'deleteSoftLineBackward':
    case 'deleteHardLineBackward':
      session.deleteBackward()
      break
    case 'deleteWordBackward':
      session.deleteBackward(true)
      break
    case 'deleteContentForward':
    case 'deleteSoftLineForward':
    case 'deleteHardLineForward':
      session.deleteForward()
      break
    case 'deleteWordForward':
      session.deleteForward(true)
      break
    default:
      break // paste and cut have their own events; undo and redo are the workspace's; formatting is not there yet
  }
}

/** Tab and Shift+Tab move a list item one level in or out; anywhere else they are the browser's (focus moves on). */
function onKeydown(event: KeyboardEvent) {
  if (fromTable(event) || event.key !== 'Tab' || event.ctrlKey || event.altKey || event.metaKey || composing) return
  adoptSelection()
  if (props.session.tab(event.shiftKey)) event.preventDefault()
}

function onCompositionStart(event: CompositionEvent) {
  if (fromTable(event)) return
  void props.session.flush()
  composing = true
}

async function onCompositionEnd(event: CompositionEvent) {
  if (fromTable(event)) return
  composing = false
  renderKey.value++ // throw away what the browser put on the page by itself
  await nextTick()
  if (event.data) props.session.type(event.data)
  placeSelection()
}

function onPaste(event: ClipboardEvent) {
  if (fromTable(event)) return
  event.preventDefault()
  adoptSelection()
  const text = event.clipboardData?.getData('text/plain')
  if (!text) return
  const at = props.session.state.selection?.focus
  // a whole fenced block (```latex … ```) is a container, not words (D560)
  if (at && text.trimStart().startsWith('`')) {
    void props.session.pasteFence(text, at).then((made) => made ?? props.session.paste(text))
    return
  }
  props.session.paste(text)
}

function onCut(event: ClipboardEvent) {
  if (fromTable(event)) return
  event.preventDefault()
  adoptSelection()
  const text = props.session.cut()
  if (text) event.clipboardData?.setData('text/plain', text)
}

function onCopy(event: ClipboardEvent) {
  if (fromTable(event)) return
  adoptSelection()
  const text = props.session.selectedText()
  if (!text) return
  event.preventDefault()
  event.clipboardData?.setData('text/plain', text)
}

function onClick(event: MouseEvent) {
  props.session.clearBack() // a click in the text is a person going on from here (D1312)
  const mark = (event.target as HTMLElement).closest<HTMLElement>('[data-sug]')
  if (mark?.dataset.sug) emit('suggestion', mark.dataset.sug)
}

/** A press anywhere but on an object, and the caret coming into the text, let go of the selected object: it was
 * selected by pointing at it, and the person has now turned to the words (its outline would otherwise stay). */
function letGoOfObject(event: Event) {
  if (state.selectedObject && letsGoOfObject(event.target as HTMLElement | null)) props.session.selectObject(null)
}

/** The top-left corner, on the screen, of the character `place` is in front of: where an object anchored there
 * hangs (D907 prints it at the same place). A paragraph with nothing to measure — no words — gives its own corner. */
function liveSpot(place: Pos): { left: number; top: number } | null {
  const el = blockEl(place.block)
  if (!el) return null
  const at = domPoint(place, false)
  if (at) {
    const range = document.createRange()
    range.setStart(at[0], at[1])
    range.collapse(true)
    const rect = [...range.getClientRects()].find((r) => r.height > 0) ?? range.getBoundingClientRect()
    if (rect.height > 0) return { left: rect.left, top: rect.top }
  }
  const box = el.getBoundingClientRect()
  return { left: box.left, top: box.top }
}

/** Where an object hangs: the place measured when the words were made to go round the objects (below), for an object
 * the words go round, else the place the words have now. */
function spotOf(place: Pos): { left: number; top: number } | null {
  const kept = wrapSpots.get(`${place.block}:${place.offset}`)
  if (!kept || !root.value) return liveSpot(place)
  const at = root.value.getBoundingClientRect() // (kept from the top left of the text, which the page scrolls)
  return { left: at.left + kept.left, top: at.top + kept.top }
}

// ------------------------------------------------------------------------------ the words go round an object
// The browser makes the lines, so an object that takes room from them (*around*, *above and below*, D1061) is told to it
// by a box that floats in the paragraph the object hangs from, as large as the room it takes (CODE-64, D1068; the
// printed pages are laid out by the engine instead, D1062). The boxes are measured one after the other, in the order of
// the text, each with those before it in place and itself out of it, so that nothing is measured against its own box
// and the same text always gives the same boxes.
/** The objects the words go round, in the order of the text. */
const hung = computed<Hung[]>(() => {
  const order = new Map(state.blocks.map((b, at) => [b.id, at]))
  const out: Hung[] = []
  for (const o of Object.values(state.objects)) {
    if (!('container' in o.anchor) || !takesRoom(wrapOf(o.anchor).wrap)) continue
    const place = props.session.placeOf(o)
    if (place) out.push({ id: o.id, block: place.block, offset: place.offset, ...wrapOf(o.anchor), dx: o.anchor.dx, dy: o.anchor.dy, w: o.w, h: o.h })
  }
  return out.sort((a, b) => (order.get(a.block) ?? 0) - (order.get(b.block) ?? 0) || a.offset - b.offset || a.id.localeCompare(b.id))
})
const wrapSlots = (block: string) => hung.value.filter((h) => h.block === block).map((h) => h.id)
const wrapFloats = shallowRef<Record<string, WrapFloat>>({})
/** Where each object the words go round hangs, from the top left of the text (the page scrolls; this does not). */
const wrapSpots = new Map<string, { left: number; top: number }>()
const wrapVersion = ref(0)
const floatOf = (id: string) => floatStyle(wrapFloats.value[id])
/** What decides how the words go round the objects; when it changes, they are measured again. */
const wrapKey = computed(() => JSON.stringify(hung.value))

/** The page as the lines are now, for `measureFloats`: the paragraphs and the boxes of the floats in the DOM. */
function pageOfWords(host: HTMLElement): WrapPage {
  const origin = () => {
    const r = host.getBoundingClientRect()
    return { left: r.left, top: r.top }
  }
  const boxes = new Map([...host.querySelectorAll<HTMLElement>('[data-wrap-float]')].map((el) => [el.dataset.for ?? '', el]))
  const length = (css: CSSStyleDeclaration, ...names: string[]) => names.reduce((sum, name) => sum + (parseFloat(css.getPropertyValue(name)) || 0), 0)
  return {
    clear: () => boxes.forEach((el) => (el.style.display = 'none')),
    origin,
    column: () => {
      const r = host.getBoundingClientRect()
      const css = getComputedStyle(host)
      return columnOf({ left: r.left, top: r.top, width: r.width, height: r.height }, parseFloat(css.paddingLeft) || 0, parseFloat(css.paddingRight) || 0)
    },
    spotOf: (block, offset) => liveSpot({ block, offset }),
    paragraphOf: (block) => {
      const el = blockEl(block)
      if (!el) return null
      const r = el.getBoundingClientRect()
      const css = getComputedStyle(el)
      return {
        left: r.left + length(css, 'padding-left', 'border-left-width'),
        top: r.top + length(css, 'padding-top', 'border-top-width'),
        width: r.width - length(css, 'padding-left', 'padding-right', 'border-left-width', 'border-right-width'),
      }
    },
    put: (id, f) => {
      const el = boxes.get(id)
      if (!el) return
      el.style.display = ''
      if (f) Object.assign(el.style, floatStyle(f))
    },
  }
}

function measureWrap() {
  const host = root.value
  if (!host) return
  const { floats, spots } = measureFloats(hung.value, pageOfWords(host))
  const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
  if (same(floats, wrapFloats.value) && same([...wrapSpots.entries()], [...spots.entries()])) return
  wrapSpots.clear()
  for (const [key, spot] of spots) wrapSpots.set(key, spot)
  wrapFloats.value = floats
  wrapVersion.value++
}
watch(wrapKey, () => nextTick(() => layoutTick.value++))
watch(layoutTick, measureWrap, { flush: 'post' })

function focus() {
  root.value?.focus()
  placeSelection()
}

/** The right button or the menu key: the style menu opens where the person pointed, or at the caret. */
function onContextMenu(event: MouseEvent) {
  if (event.shiftKey && event.clientX !== 0) return // Shift + right button: the browser's own menu (spelling, copy link…), as everywhere
  // A floating object and a table have a menu of their own (D1225, D1224): the press is theirs, it never reaches the
  // words below, so no paragraph menu opens here. They take it from here: this capture handler only steps aside.
  if ((event.target as Element | null)?.closest?.('[data-object]')) return
  event.preventDefault()
  const atom = (event.target as HTMLElement).closest<HTMLElement>('[data-atom]')
  const at = atom?.closest<HTMLElement>('[data-block]')?.dataset.block
  if (atom && at) {
    // on a reference: its own menu (Show As, Go to Target, Remove), mock-up C
    props.session.setSelection({ block: at, offset: Number(atom.dataset.off) }, { block: at, offset: Number(atom.dataset.off) + 1 })
    emit('reference-menu', { block: at, index: Number(atom.dataset.field), x: event.clientX, y: event.clientY })
    return
  }
  adoptSelection(true)
  const keyboard = event.clientX === 0 && event.clientY === 0
  const rect = keyboard ? document.getSelection()?.rangeCount ? document.getSelection()!.getRangeAt(0).getClientRects()[0] : undefined : undefined
  emit('style-menu', rect ? { x: rect.left, y: rect.bottom + 6 } : { x: event.clientX, y: event.clientY })
}

/** The place of the text nearest a point of the screen (where a dropped object hangs, D1023): the paragraph by its
 * height, and within it the character the browser says the point is over; the start of the paragraph where the point
 * is not over its words. The object layers are let through for a moment, so that the words under a dragged object answer. */
function placeAt(x: number, y: number): Pos | null {
  const blocks = [...(root.value?.querySelectorAll<HTMLElement>('[data-block]') ?? [])].map((el) => {
    const r = el.getBoundingClientRect()
    return { id: el.dataset.block!, top: r.top, bottom: r.bottom }
  })
  const id = nearestBlock(blocks, y)
  const el = id ? blockEl(id) : null
  if (!id || !el) return null
  const r = el.getBoundingClientRect()
  if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) {
    const layers = [...(scroller.value?.querySelectorAll<HTMLElement>('[data-testid^="containers"]') ?? [])]
    const kept = layers.map((l) => l.style.visibility)
    layers.forEach((l) => (l.style.visibility = 'hidden'))
    try {
      const hit = document.caretPositionFromPoint?.(x, y)
      const found = hit ? ([hit.offsetNode, hit.offset] as const) : null
      const pos = found && el.contains(found[0]) ? posFromDom(found[0], found[1]) : null
      if (pos && pos.block === id) return pos
    } finally {
      layers.forEach((l, i) => (l.style.visibility = kept[i]!))
    }
  }
  return { block: id, offset: 0 }
}

/** Where the caret is on the window (to open the style menu from the keyboard or a menu). */
function caretPoint(): { x: number; y: number } {
  const range = document.getSelection()?.rangeCount ? document.getSelection()!.getRangeAt(0) : null
  const rect = range?.getClientRects()[0] ?? range?.getBoundingClientRect()
  const box = scroller.value?.getBoundingClientRect()
  if (rect && (rect.width || rect.height || rect.top)) return { x: rect.left, y: rect.bottom + 6 }
  return { x: (box?.left ?? 0) + 60, y: (box?.top ?? 0) + 60 }
}

/** What a screen reader says for a reference: what it points at and reads as, or that it is missing. */
function referenceLabel(seg: FieldSeg): string {
  if (seg.state === 'broken') return t('missing reference')
  return t('Reference to {what}', { what: seg.text || t('a page') })
}
function referenceTitle(seg: FieldSeg): string {
  if (seg.state === 'broken') return t('What this reference points at was deleted')
  if (seg.state === 'page') return props.pages?.get(seg.target) ? t('Ctrl+click to go there') : t('The page is known in Page view and when printing')
  return t('Ctrl+click to go there')
}
/** Ctrl+click on a reference goes to what it points at (mock-up D); a plain click puts the caret after it. */
function onReferenceClick(event: MouseEvent, seg: FieldSeg) {
  if (!(event.ctrlKey || event.metaKey) || seg.state === 'broken') return
  event.preventDefault()
  goTo(seg.target)
}

/** Follow an entry of a table of contents: the caret goes to the start of its heading (E9.31). */
function goTo(target: string) {
  if (!state.blocks.some((b) => b.id === target)) return // a reference to an object or a slide: nothing to scroll to here
  props.session.setSelection({ block: target, offset: 0 })
  scrollToBlock(target)
  focus()
}

/** The page a table's entry leads to, in Page view once the text is laid out (step F); `null` in flow, which has no
 * pages, and for a table that shows none. */
function pageOf(block: Block, target: string): number | null {
  return (block.generated?.places && props.pages?.get(target)) || null
}

/** What a table's chip says: what it is and the levels it lists. */
function chipOf(block: Block): string {
  const g = block.generated!
  const levels = g.first === g.last ? t('level {n}', { n: g.first }) : t('levels {first}–{last}', { first: g.first, last: g.last })
  return `${t('Table of contents')} · ${levels}`
}

/** Show a paragraph (a search found something in an object that hangs from it) without moving the caret. */
function scrollToBlock(id: string) {
  blockEl(id)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

/** The paragraph at the top of what is in sight: where the person was, for "Back where I was" (D1312). */
function firstVisibleBlock(): string | null {
  const top = scroller.value?.getBoundingClientRect().top ?? 0
  for (const el of root.value?.querySelectorAll<HTMLElement>('[data-block]') ?? []) {
    if (el.getBoundingClientRect().bottom > top) return el.dataset.block ?? null
  }
  return null
}
watch(
  () => props.session.state.scrollBack,
  (back) => {
    if (back) blockEl(back.anchor)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  },
)

// A tag in the chat that points at a paragraph marks it (D554); one that points at something hanging from a paragraph
// brings the paragraph into view.
usePointed(props.session.state, root, (id) => `[data-block="${CSS.escape(id)}"]`)
watch(
  () => props.session.state.pointed,
  (pointed) => {
    if (pointed?.container) scrollToBlock(pointed.container)
  },
)

// The match being looked at comes into view; the caret stays where it was, so that a person can go on typing.
watch(
  () => props.marks?.findIndex((m) => m.current) ?? -1,
  async (index) => {
    if (index < 0) return
    await nextTick()
    root.value?.querySelector<HTMLElement>('[data-found="current"]')?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  },
)

function scrollToSuggestion(id: string) {
  const mark = root.value?.querySelector<HTMLElement>(`[data-sug="${CSS.escape(id)}"]`)
  mark?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

/** Take over where the caret is on the page right now. The page tells us of a move only a moment later (`selectionchange`
 *  is queued), so a command that works at the caret and opens a dialog first asks for this before the dialog takes the
 *  focus away: otherwise it acts where the caret was a moment ago. */
function syncCaret() {
  adoptSelection(true)
}
defineExpose({ focus, scrollToSuggestion, scrollToBlock, caretPoint, goTo, syncCaret })
</script>

<template>
  <div ref="scroller" class="scroller" :class="view" data-testid="text-scroller" @contextmenu.capture="onContextMenu" @pointerdown.capture="letGoOfObject" @focusin="letGoOfObject">
    <div class="sheet">
      <TextContainers behind :session="session" :host="root" :tick="layoutTick + wrapVersion" :spot-of="spotOf" :place-at="placeAt" :turning="turning" @menu="emit('object-menu', $event)" @leave="focus()" />
      <div
        :key="renderKey"
        ref="root"
        class="doc"
        :class="{ authors }"
        :contenteditable="!session.readOnly"
        role="textbox"
        aria-multiline="true"
        :aria-label="t('the text')"
        :aria-readonly="session.readOnly"
        spellcheck="true"
        data-testid="text"
        @beforeinput="onBeforeInput"
        @keydown="onKeydown"
        @compositionstart="onCompositionStart"
        @compositionend="onCompositionEnd"
        @paste="onPaste"
        @cut="onCut"
        @copy="onCopy"
        @click="onClick"
        @drop.prevent
        @dragstart.prevent
        @blur="session.flush()"
      >
        <template v-for="(block, at) in state.blocks" :key="`${block.id}:${block.generated ? 'nav' : tagOf(block.style)}`">
        <!-- a table of contents (E9.31): a navigation landmark of links, not text; the caret steps over it -->
        <nav
          v-if="block.generated"
          class="para toc"
          :class="[`st-${block.style}`, { picked: state.selection?.focus.block === block.id }, replayClass(block.id)]"
          contenteditable="false"
          :data-block="block.id"
          :aria-label="t('Table of contents')"
          data-testid="contents"
          @keydown.stop
        >
          <a
            v-for="entry in block.entries ?? []"
            :key="entry.target"
            data-skip
            class="toc-entry"
            :class="`st-${entry.style}`"
            :style="cssOf(entry.style)"
            :href="`#${entry.target}`"
            @click.prevent.stop="goTo(entry.target)"
            ><span v-if="entry.number" class="toc-number">{{ entry.number }}</span><span class="toc-words">{{ entry.text }}</span
            ><template v-if="pageOf(block, entry.target)"
              ><span class="toc-leader" :style="leaderCss(block.generated.leader)" aria-hidden="true" /><span class="toc-page">{{ pageOf(block, entry.target) }}</span></template
            ></a
          >
          <p v-if="!block.entries?.length" data-skip class="toc-empty">{{ t('No headings yet: the table lists them as they are written.') }}</p>
          <button type="button" data-skip class="toc-chip" data-testid="contents-chip" @click.stop="emit('contents', block.id)">
            {{ chipOf(block) }} · {{ t('Options…') }}
          </button>
        </nav>
        <component
          :is="tagOf(block.style)"
          v-else
          class="para"
          :class="[`st-${block.style}`, { item: block.item, numbered: !block.item && block.label }, replayClass(block.id)]"
          :style="{ ...cssOf(block.style), ...layoutOf(at) }"
          v-bind="headingOf(block.style)"
          :data-block="block.id"
          :data-marker="block.label?.marker"
        >
          <span
            v-for="id in wrapSlots(block.id)"
            :key="`float-${id}`"
            data-skip
            data-wrap-float
            :data-for="id"
            contenteditable="false"
            aria-hidden="true"
            class="wrap-float"
            :style="floatOf(id)"
          />
          <template v-for="seg in segmentsOf(block)" :key="seg.key">
            <span
              v-if="seg.kind === 'text'"
              data-seg
              :data-off="seg.start"
              :data-sug="seg.sug ?? undefined"
              :data-found="seg.found ?? undefined"
              class="seg"
              :class="{ by: authors && seg.author, via: authors && seg.via, sug: seg.sug, remark: seg.remark, hot: seg.sug && seg.sug === active, zone: seg.zone, found: seg.found, now: seg.found === 'current' }"
              :style="{ '--a': seg.author ? colorOf(state, seg.author) : undefined, '--c': seg.zone ?? undefined }"
              :title="title(seg)"
              >{{ seg.text }}</span
            >
            <span
              v-else-if="seg.kind === 'field'"
              data-atom
              :data-off="seg.start"
              :data-field="seg.index"
              :data-thing="seg.target"
              contenteditable="false"
              class="ref"
              :class="seg.state"
              role="link"
              :aria-label="referenceLabel(seg)"
              :title="referenceTitle(seg)"
              @click="onReferenceClick($event, seg)"
              ><template v-if="seg.state === 'broken'">⚠ {{ t('missing reference') }}</template><template v-else-if="seg.state === 'page'">{{ pages?.get(seg.target) ?? '#' }}</template><template v-else>{{ seg.text || '#' }}</template></span
            >
            <span v-else-if="seg.kind === 'overlay'" data-skip data-overlay :data-at="seg.at" class="overlay" :style="{ '--a': colorOf(state, state.me.user) }">{{ seg.text }}</span>
            <span v-else-if="seg.kind === 'reply'" data-skip contenteditable="false" class="reply" :data-sug="seg.id" :class="{ hot: seg.id === active }" @click.stop="emit('suggestion', seg.id!)">{{ seg.text }}</span>
            <span v-else data-skip contenteditable="false" class="peer-caret" :style="{ '--c': seg.color }"><i /><b>{{ seg.text }}</b></span>
          </template>
          <br v-if="!block.text && !hasOverlay(block)" data-skip >
        </component>
        <!-- the tables that hang from this paragraph, in the flow after it (E9.32): a real table, boxes edited in place -->
        <TableView
          v-for="shown in tablesAfter(block.id)"
          :key="shown.object.id"
          :session="session"
          :object="shown.object"
          :table="shown.table"
          @options="emit('table-options', $event)"
          @menu="emit('object-menu', $event)"
          @leave="focus()"
        />
        </template>
      </div>
      <TextContainers :session="session" :host="root" :tick="layoutTick + wrapVersion" :spot-of="spotOf" :place-at="placeAt" :turning="turning" @menu="emit('object-menu', $event)" @leave="focus()" />
    </div>
  </div>
</template>

<style scoped>
.scroller {
  overflow: auto;
  min-height: 0;
  background: var(--page);
}
.sheet {
  position: relative; /* the containers float over it (D560) */
  margin: 0 auto;
  padding: 36px 40px 160px;
  max-width: 820px;
}
.scroller.page {
  background: color-mix(in srgb, var(--ink) 7%, var(--paper));
  padding: 28px 0;
}
.scroller.page .sheet {
  width: min(816px, calc(100% - 32px));
  min-height: 1056px;
  padding: 96px 96px 120px;
  background: var(--surface);
  box-shadow: var(--shadow);
  border-radius: 2px;
}
.doc {
  position: relative; /* over the layer of the objects behind the words, under the one over them (TextContainers.vue) */
  z-index: 1;
  outline: none;
  font: 400 16.5px/1.75 var(--font-ui);
  color: var(--text);
  white-space: pre-wrap;
  word-wrap: break-word;
  min-height: 12rem;
  caret-color: var(--app);
}
.doc :deep(.para) {
  margin: 0 0 0.9em;
}

/* the room an object takes from the lines (CODE-64): a box that only the lines notice. It floats to a side of its
   paragraph, its size and place come inline from `measureWrap`. */
.doc :deep(.wrap-float) {
  display: block;
  margin: 0;
  padding: 0;
  pointer-events: none;
  user-select: none;
}

/* a list item: the marker is drawn, not typed, in the gutter before the text (E9.21). It is not part of the text, so
   selection, copy, find and the caret never see it. */
/* its padding and the gap to the next item come inline from `itemLayout`, after the style's own CSS */
.doc :deep(.para.item) {
  position: relative;
}
.doc :deep(.para.item[data-marker]::before) {
  content: attr(data-marker);
  position: absolute;
  left: var(--item-left);
  width: var(--item-step);
  box-sizing: border-box;
  padding-right: var(--marker-gap); /* MARKER_GAP_EM of the layout library: the printed pages use the same */
  text-align: right;
  white-space: nowrap;
  font-weight: 400;
  font-style: normal;
  user-select: none;
  pointer-events: none;
}

/* a numbered heading (E9.22): its number, derived from its style, hangs before it in its own look, a marker gap away
   (as the printed pages draw it). Like a list marker it is never part of the text. */
.doc :deep(.para.numbered) {
  position: relative;
}
.doc :deep(.para.numbered[data-marker]::before) {
  content: attr(data-marker);
  position: absolute;
  right: 100%;
  padding-right: var(--marker-gap); /* MARKER_GAP_EM, from `headingNumberLayout` */
  white-space: nowrap;
  user-select: none;
  pointer-events: none;
}

/* a table of contents (E9.31): its entries are drawn in their Contents styles, as links; no pages in flow */
.doc :deep(nav.toc) {
  position: relative;
  margin: 4px 0 12px;
  padding: 6px 8px 34px;
  border-radius: 6px;
  outline: 1px dashed transparent;
  user-select: none;
}
.doc :deep(nav.toc:hover),
.doc :deep(nav.toc.picked) {
  outline-color: color-mix(in srgb, var(--app) 55%, transparent);
}
.doc :deep(nav.toc.picked) {
  background: color-mix(in srgb, var(--app) 7%, transparent);
}
.doc :deep(.toc-entry) {
  display: flex;
  align-items: baseline;
  color: inherit;
  text-decoration: none;
}
.doc :deep(.toc-words) {
  min-width: 0;
}
.doc :deep(.toc-page) {
  min-width: 2em;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.doc :deep(.toc-entry:hover),
.doc :deep(.toc-entry:focus-visible) {
  text-decoration: underline;
}
.doc :deep(.toc-number) {
  display: inline-block;
  min-width: 2.2em;
  font-variant-numeric: tabular-nums;
}
.doc :deep(.toc-empty) {
  margin: 0;
  color: var(--muted);
  font-style: italic;
}
.doc :deep(.toc-chip) {
  position: absolute;
  left: 8px;
  bottom: 6px;
  font: inherit;
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  border: 1px solid var(--line-field); /* a control's edge: 3:1 (BITV 1.4.11) */
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
}
.doc :deep(.toc-chip:hover),
.doc :deep(.toc-chip:focus-visible) {
  color: var(--ink);
  border-color: var(--app);
}

/* a reference (step H): a quiet iris underline; broken, a dashed rose one with a sign (never colour alone) */
.doc :deep(.ref) {
  border-bottom: 1.5px solid var(--iris);
  cursor: pointer;
  user-select: all;
}
.doc :deep(.ref.page) {
  color: var(--muted);
}
.doc :deep(.ref.broken) {
  color: var(--danger);
  border-bottom: 1.5px dashed var(--danger);
}

/* who wrote what */
.by {
  background: color-mix(in srgb, var(--a) 13%, transparent);
  border-bottom: 2px solid var(--a);
}
.via {
  border-bottom-style: dotted;
}
.overlay {
  background: color-mix(in srgb, var(--a, var(--app)) 10%, transparent);
}

/* what a search found (E9.28): a band and an underline, never colour alone; the one being looked at has an outline too */
.found {
  background: color-mix(in srgb, var(--purpose-input) 55%, transparent);
  border-bottom: 3px solid var(--app);
}
.found.now {
  outline: 2px solid var(--ink);
  outline-offset: 1px;
  background: color-mix(in srgb, var(--purpose-input) 80%, transparent);
}

/* colleagues in the text */
.zone {
  background: color-mix(in srgb, var(--c) 14%, transparent);
  border-bottom: 2px solid var(--c);
  border-radius: 2px;
}
.peer-caret {
  position: relative;
  display: inline-block;
  width: 0;
  height: 1em;
  vertical-align: baseline;
  pointer-events: none;
  user-select: none;
}
.peer-caret i {
  position: absolute;
  left: -1px;
  top: -0.2em;
  width: 2px;
  height: 1.45em;
  background: var(--c);
  border-radius: 1px;
}
.peer-caret b {
  position: absolute;
  left: -1px;
  top: -1.6em;
  padding: 0 6px;
  font: 600 11px/18px var(--font-ui);
  color: #fff;
  background: var(--c);
  border-radius: 5px 5px 5px 0;
  white-space: nowrap;
}

/* what the assistant suggests */
.sug {
  cursor: pointer;
  background: color-mix(in srgb, var(--iris) 9%, transparent);
  border-radius: 3px;
}
.sug:not(.remark) {
  text-decoration: line-through;
  text-decoration-color: var(--iris);
  text-decoration-thickness: 1.5px;
}
.sug.remark {
  text-decoration: underline wavy var(--iris);
  text-underline-offset: 3px;
}
.sug.hot,
.reply.hot {
  outline: 2px solid color-mix(in srgb, var(--iris) 55%, transparent);
}
.reply {
  margin-left: 3px;
  padding: 0 4px;
  color: #4a3aa8;
  background: color-mix(in srgb, var(--iris) 14%, transparent);
  border-radius: 4px;
  font-weight: 500;
  cursor: pointer;
  user-select: none;
}
</style>
