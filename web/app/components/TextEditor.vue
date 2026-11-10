<script setup lang="ts">
// The text, drawn from the session's replica. The browser never changes it: every input is caught (`beforeinput`), turned
// into a request, and the text appears when the server's events arrive. What is typed but not yet sent is drawn at the
// caret as an overlay. Selections are translated between the page and the model (paragraph, offset).
import { nextTick, onBeforeUnmount, onBeforeUpdate, onMounted, onUpdated, ref, watch } from 'vue'
import { colorOf } from '~/lib/people'
import type { Block, Pos } from '~/lib/blocks'
import { paragraphCss, semanticTag } from '~/lib/style-css'
import type { TextSession } from '~/lib/text-session'

const props = defineProps<{ session: TextSession; view: 'flow' | 'page'; authors: boolean; active: string | null }>()
const emit = defineEmits<{ suggestion: [id: string]; 'style-menu': [at: { x: number; y: number }] }>()

const state = props.session.state
const root = ref<HTMLElement | null>(null)
const scroller = ref<HTMLElement | null>(null)
const renderKey = ref(0)
let composing = false
// A paragraph is drawn from the CSS of its style (D73); the element only says what it is (a heading, a quote).
const tagOf = (style: string) => semanticTag(state.styles, style)
// `resolved`, not `computed`: a palette role is a colour by the time it reaches the page (D200).
const cssOf = (style: string) => paragraphCss(state.styles.find((s) => s.id === style)?.resolved ?? {})

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
}
interface OtherSeg {
  kind: 'overlay' | 'caret' | 'reply'
  key: string
  text: string
  color?: string
  at?: number
  id?: string
}
type Seg = TextSeg | OtherSeg

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
    })
  })
  return out
}

const hasOverlay = (block: Block) => [state.sending, state.pending].some((u) => u && u.at.block === block.id)

function title(seg: TextSeg): string | undefined {
  if (seg.via) return `${seg.author ?? 'someone'}, from a suggestion of ${seg.via}`
  if (props.authors && seg.author) return `written by ${seg.author}`
  return seg.zoneOwner ? `${seg.zoneOwner} is writing here` : undefined
}

// ------------------------------------------------------------------------------ page <-> model
const blockEl = (id: string) => root.value?.querySelector<HTMLElement>(`[data-block="${CSS.escape(id)}"]`) ?? null

/** How many characters of the text (not counting what only the screen shows) lie before a point of the page. */
function textBefore(el: HTMLElement, node: Node, offset: number): number {
  const range = document.createRange()
  range.selectNodeContents(el)
  range.setEnd(node, offset)
  let count = 0
  const walk = (n: Node) => {
    if (n.nodeType === Node.TEXT_NODE) count += (n as Text).data.length
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
  const segs = [...el.querySelectorAll<HTMLElement>('[data-seg]')]
  if (!segs.length) return [el, 0]
  const found = segs.find((s) => pos.offset < Number(s.dataset.off) + (s.textContent?.length ?? 0)) ?? segs.at(-1)!
  return [found.firstChild!, Math.max(0, Math.min(pos.offset - Number(found.dataset.off), (found.textContent ?? '').length))]
}

function placeSelection() {
  const container = root.value
  const sel = document.getSelection()
  const mine = state.selection
  if (!container || !sel || !mine || composing) return
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
onMounted(() => document.addEventListener('selectionchange', onSelectionChange))
onBeforeUnmount(() => document.removeEventListener('selectionchange', onSelectionChange))

// ------------------------------------------------------------------------------ input
function onBeforeInput(event: InputEvent) {
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

function onCompositionStart() {
  void props.session.flush()
  composing = true
}

async function onCompositionEnd(event: CompositionEvent) {
  composing = false
  renderKey.value++ // throw away what the browser put on the page by itself
  await nextTick()
  if (event.data) props.session.type(event.data)
  placeSelection()
}

function onPaste(event: ClipboardEvent) {
  event.preventDefault()
  adoptSelection()
  const text = event.clipboardData?.getData('text/plain')
  if (text) props.session.paste(text)
}

function onCut(event: ClipboardEvent) {
  event.preventDefault()
  adoptSelection()
  const text = props.session.cut()
  if (text) event.clipboardData?.setData('text/plain', text)
}

function onCopy(event: ClipboardEvent) {
  adoptSelection()
  const text = props.session.selectedText()
  if (!text) return
  event.preventDefault()
  event.clipboardData?.setData('text/plain', text)
}

function onClick(event: MouseEvent) {
  const mark = (event.target as HTMLElement).closest<HTMLElement>('[data-sug]')
  if (mark?.dataset.sug) emit('suggestion', mark.dataset.sug)
}

function focus() {
  root.value?.focus()
  placeSelection()
}

/** The right button or the menu key: the style menu opens where the person pointed, or at the caret. */
function onContextMenu(event: MouseEvent) {
  if (event.shiftKey && event.clientX !== 0) return // Shift + right button: the browser's own menu (spelling, copy link…), as everywhere
  event.preventDefault()
  adoptSelection(true)
  const keyboard = event.clientX === 0 && event.clientY === 0
  const rect = keyboard ? document.getSelection()?.rangeCount ? document.getSelection()!.getRangeAt(0).getClientRects()[0] : undefined : undefined
  emit('style-menu', rect ? { x: rect.left, y: rect.bottom + 6 } : { x: event.clientX, y: event.clientY })
}

/** Where the caret is on the window (to open the style menu from the keyboard or a menu). */
function caretPoint(): { x: number; y: number } {
  const range = document.getSelection()?.rangeCount ? document.getSelection()!.getRangeAt(0) : null
  const rect = range?.getClientRects()[0] ?? range?.getBoundingClientRect()
  const box = scroller.value?.getBoundingClientRect()
  if (rect && (rect.width || rect.height || rect.top)) return { x: rect.left, y: rect.bottom + 6 }
  return { x: (box?.left ?? 0) + 60, y: (box?.top ?? 0) + 60 }
}

function scrollToSuggestion(id: string) {
  const mark = root.value?.querySelector<HTMLElement>(`[data-sug="${CSS.escape(id)}"]`)
  mark?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

defineExpose({ focus, scrollToSuggestion, caretPoint })
</script>

<template>
  <div ref="scroller" class="scroller" :class="view" data-testid="text-scroller" @contextmenu.capture="onContextMenu">
    <div class="sheet">
      <div
        :key="renderKey"
        ref="root"
        class="doc"
        :class="{ authors }"
        :contenteditable="!session.readOnly"
        role="textbox"
        aria-multiline="true"
        aria-label="the text"
        :aria-readonly="session.readOnly"
        spellcheck="true"
        data-testid="text"
        @beforeinput="onBeforeInput"
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
        <component :is="tagOf(block.style)" v-for="block in state.blocks" :key="`${block.id}:${tagOf(block.style)}`" class="para" :class="`st-${block.style}`" :style="cssOf(block.style)" :data-block="block.id">
          <template v-for="seg in segmentsOf(block)" :key="seg.key">
            <span
              v-if="seg.kind === 'text'"
              data-seg
              :data-off="seg.start"
              :data-sug="seg.sug ?? undefined"
              class="seg"
              :class="{ by: authors && seg.author, via: authors && seg.via, sug: seg.sug, remark: seg.remark, hot: seg.sug && seg.sug === active, zone: seg.zone }"
              :style="{ '--a': seg.author ? colorOf(state, seg.author) : undefined, '--c': seg.zone ?? undefined }"
              :title="title(seg)"
              >{{ seg.text }}</span
            >
            <span v-else-if="seg.kind === 'overlay'" data-skip data-overlay :data-at="seg.at" class="overlay" :style="{ '--a': colorOf(state, state.me.user) }">{{ seg.text }}</span>
            <span v-else-if="seg.kind === 'reply'" data-skip contenteditable="false" class="reply" :class="{ hot: seg.id === active }" @click.stop="emit('suggestion', seg.id!)">{{ seg.text }}</span>
            <span v-else data-skip contenteditable="false" class="peer-caret" :style="{ '--c': seg.color }"><i /><b>{{ seg.text }}</b></span>
          </template>
          <br v-if="!block.text && !hasOverlay(block)" data-skip />
        </component>
      </div>
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
