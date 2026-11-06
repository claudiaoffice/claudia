<script setup lang="ts">
// The slide on screen: its objects, and what people do to them. A click selects (and holds) an object, dragging moves
// it, the handles resize it, a double click or Enter edits its text, Delete removes it. Nothing is believed until the
// server says so: while the pointer is down the frame is a preview here, and it is committed when the pointer is up.
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { CORNERS, HANDLES, SLIDE_H, SLIDE_W, fitScale, moveFrame, resizeFrame, toSlide, type Frame, type Handle } from '~/lib/geometry'
import { colorOf, inkOn } from '~/lib/people'
import { pathCss, scaleCss, textCss } from '~/lib/slide-style'
import { withDisplayInk } from '~/lib/style-css'
import type { SlideObject, SlideSession } from '~/lib/slide-session'

const props = defineProps<{ session: SlideSession }>()
const session = props.session
const state = session.state

const MARGIN = 24
const DRAG_START = 3 // screen pixels the pointer must travel before a click becomes a drag

const area = ref<HTMLElement | null>(null)
const slideEl = ref<HTMLElement | null>(null)
const editor = ref<HTMLTextAreaElement | null>(null)
const size = ref({ w: 1200, h: 700 })
const scale = computed(() => fitScale(size.value, MARGIN))
const readonly = computed(() => state.me.role === 'viewer')

const objects = computed(() => session.objectsOn(state.activeSlide))
const others = computed(() => session.selectedByOthers(state.activeSlide))

// ------------------------------------------------------------------------------ the screen scale
let watcher: ResizeObserver | null = null
onMounted(() => {
  if (!area.value) return
  const measure = () => (size.value = { w: area.value!.clientWidth, h: area.value!.clientHeight })
  measure()
  watcher = new ResizeObserver(measure)
  watcher.observe(area.value)
})
onBeforeUnmount(() => watcher?.disconnect())

// ------------------------------------------------------------------------------ how objects look
const px = (units: number) => `${Math.round(units * scale.value * 100) / 100}px`

/** Where an object is on the screen; a frame being dragged replaces the one the server knows. */
function frameOf(o: SlideObject): Frame {
  return drag.value?.id === o.id ? drag.value.frame : o
}
function boxStyle(o: SlideObject) {
  const f = frameOf(o)
  return { left: px(f.x), top: px(f.y), width: px(f.w), height: px(f.h) }
}
function cssOf(o: SlideObject) {
  // withDisplayInk: a text object's default ink, genuinely black in the document (D28/2026-11-06), still needs to
  // read against a dark slide canvas in dark mode — display-only, same fix as composes' paragraphCss.
  return withDisplayInk(scaleCss(state.styles[o.style]?.css ?? {}, scale.value))
}
function outline(o: SlideObject) {
  return o.shape ? (state.shapes[o.shape] ?? null) : null
}
function textBox(o: SlideObject) {
  const area = outline(o)?.text_area ?? { x: 0, y: 0, w: 100, h: 100 }
  const pad = o.kind === 'text' ? 0 : 8 // a shape's text is not written right up to its edge
  const f = frameOf(o)
  return {
    left: `calc(${(area.x / 100) * f.w * scale.value}px + ${pad * scale.value}px)`,
    top: `calc(${(area.y / 100) * f.h * scale.value}px + ${pad * scale.value}px)`,
    width: `calc(${(area.w / 100) * f.w * scale.value}px - ${2 * pad * scale.value}px)`,
    height: `calc(${(area.h / 100) * f.h * scale.value}px - ${2 * pad * scale.value}px)`,
  }
}
function textStyle(o: SlideObject): Record<string, string> {
  const centered = o.kind === 'shape'
  return { ...textCss(cssOf(o)), display: 'flex', 'flex-direction': 'column', 'justify-content': centered ? 'center' : 'flex-start', ...textBox(o) }
}
function editorStyle(o: SlideObject): Record<string, string> {
  return { ...textCss(cssOf(o)), ...textBox(o) }
}
const label = (o: SlideObject) => (o.kind === 'text' ? 'Text box' : (outline(o)?.name ?? 'Shape')) + (o.text ? `: ${o.text}` : '')

// ------------------------------------------------------------------------------ selection, dragging, resizing
type Drag = { id: string; handle: Handle | 'move'; from: { x: number; y: number }; start: Frame; frame: Frame; moved: boolean }
const drag = ref<Drag | null>(null)

const selected = computed(() => (state.selected ? (state.objects[state.selected] ?? null) : null))
const selectedFrame = computed(() => (selected.value ? frameOf(selected.value) : null))
const handles = computed<Handle[]>(() => {
  const o = selected.value
  if (!o || readonly.value || editing.value) return []
  return outline(o)?.aspect ? CORNERS : HANDLES
})
const aspectOf = (o: SlideObject) => outline(o)?.aspect ?? null

function point(event: PointerEvent) {
  const box = slideEl.value!.getBoundingClientRect()
  return toSlide(event.clientX, event.clientY, box, scale.value)
}

async function onObjectDown(event: PointerEvent, o: SlideObject) {
  if (event.button !== 0) return
  event.stopPropagation()
  if (editing.value && editing.value.id === o.id) return
  const target = event.currentTarget as HTMLElement
  const where = point(event)
  target.setPointerCapture(event.pointerId)
  await commitEdit()
  area.value?.focus({ preventScroll: true })
  drag.value = { id: o.id, handle: 'move', from: where, start: { x: o.x, y: o.y, w: o.w, h: o.h }, frame: { x: o.x, y: o.y, w: o.w, h: o.h }, moved: false }
  session.select(o.id)
}

function onHandleDown(event: PointerEvent, handle: Handle) {
  const o = selected.value
  if (!o || event.button !== 0) return
  event.stopPropagation()
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  drag.value = { id: o.id, handle, from: point(event), start: { x: o.x, y: o.y, w: o.w, h: o.h }, frame: { x: o.x, y: o.y, w: o.w, h: o.h }, moved: false }
}

function onPointerMove(event: PointerEvent) {
  const d = drag.value
  if (!d || readonly.value) return
  const here = point(event)
  const [dx, dy] = [here.x - d.from.x, here.y - d.from.y]
  if (!d.moved && Math.hypot(dx, dy) * scale.value < DRAG_START) return
  d.moved = true
  const o = state.objects[d.id]
  if (!o) return
  d.frame = d.handle === 'move' ? moveFrame(d.start, dx, dy) : resizeFrame(d.start, d.handle, dx, dy, aspectOf(o))
}

async function onPointerUp() {
  const d = drag.value
  if (!d) return
  const changed = d.moved && (d.frame.x !== d.start.x || d.frame.y !== d.start.y || d.frame.w !== d.start.w || d.frame.h !== d.start.h)
  if (changed && !readonly.value) {
    if (d.handle === 'move') await session.move(d.id, d.frame.x, d.frame.y)
    else await session.resize(d.id, d.frame)
  }
  if (drag.value === d) drag.value = null // the server's answer is in the state by now; a refusal snaps the object back
}

/** A press on the slide itself, not on an object: nothing is selected any more. */
async function onSlideDown(event: PointerEvent) {
  if (event.button !== 0) return
  await commitEdit()
  area.value?.focus({ preventScroll: true })
  session.select(null)
}

// ------------------------------------------------------------------------------ editing text
const editing = ref<{ id: string; text: string } | null>(null)
const editText = computed({
  get: () => editing.value?.text ?? '',
  set: (text: string) => editing.value && (editing.value.text = text),
})
const setEditor = (el: unknown) => {
  if (el) editor.value = el as HTMLTextAreaElement
}

async function beginEdit(id: string | null = state.selected) {
  const o = id ? state.objects[id] : null
  if (!o || editing.value) return
  if (readonly.value) return session.notice('You can only look at this document.', 'warning')
  await session.select(o.id)
  if (state.selected !== o.id) return // a colleague holds it
  editing.value = { id: o.id, text: o.text }
  await nextTick()
  editor.value?.focus()
  editor.value?.setSelectionRange(o.text.length, o.text.length)
}

async function commitEdit() {
  const e = editing.value
  if (!e) return
  editing.value = null
  area.value?.focus({ preventScroll: true })
  if (state.objects[e.id] && e.text !== state.objects[e.id]!.text) await session.setText(e.id, e.text)
}

function cancelEdit() {
  if (!editing.value) return
  editing.value = null
  area.value?.focus({ preventScroll: true })
}

function onEditorKey(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    commitEdit()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    cancelEdit()
  }
  event.stopPropagation()
}

// ------------------------------------------------------------------------------ keys
const STEP = 10

async function onKey(event: KeyboardEvent) {
  const o = selected.value
  if (editing.value) return
  if (event.key === 'Escape') return void session.select(null)
  if (!o) return
  if (event.key === 'Enter' || event.key === 'F2') {
    event.preventDefault()
    return void beginEdit()
  }
  if (readonly.value) return
  if (event.key === 'Delete' || event.key === 'Backspace') {
    event.preventDefault()
    return void session.remove(o.id)
  }
  const arrows: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }
  const arrow = arrows[event.key]
  if (arrow) {
    event.preventDefault()
    const step = event.shiftKey ? 1 : STEP
    const f = moveFrame(o, arrow[0] * step, arrow[1] * step)
    if (f.x !== o.x || f.y !== o.y) await session.move(o.id, f.x, f.y)
  }
}

defineExpose({ focus: () => area.value?.focus(), beginEdit })

const HANDLE_CURSOR: Record<Handle, string> = { nw: 'nwse-resize', se: 'nwse-resize', ne: 'nesw-resize', sw: 'nesw-resize', n: 'ns-resize', s: 'ns-resize', e: 'ew-resize', w: 'ew-resize' }
const HANDLE_AT: Record<Handle, [number, number]> = { nw: [0, 0], n: [0.5, 0], ne: [1, 0], e: [1, 0.5], se: [1, 1], s: [0.5, 1], sw: [0, 1], w: [0, 0.5] }
const handleStyle = (h: Handle) => ({ left: `${HANDLE_AT[h][0] * 100}%`, top: `${HANDLE_AT[h][1] * 100}%`, cursor: HANDLE_CURSOR[h] })
</script>

<template>
  <div
    ref="area"
    class="area"
    tabindex="0"
    aria-label="slide"
    @keydown="onKey"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
  >
    <div
      ref="slideEl"
      class="slide"
      data-testid="slide"
      :data-slide="state.activeSlide"
      :style="{ width: px(SLIDE_W), height: px(SLIDE_H) }"
      @pointerdown="onSlideDown"
    >
      <div
        v-for="o in objects"
        :key="o.id"
        class="obj"
        :class="[o.kind, { selected: o.id === state.selected, empty: o.text === '' }]"
        :style="boxStyle(o)"
        :data-id="o.id"
        :aria-label="label(o)"
        role="button"
        @pointerdown="onObjectDown($event, o)"
        @dblclick.stop="beginEdit(o.id)"
      >
        <svg v-if="outline(o)" class="shape" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path :d="outline(o)!.path" vector-effect="non-scaling-stroke" :style="pathCss(cssOf(o))" />
        </svg>
        <div class="words" :style="textStyle(o)">
          <span v-if="o.text === '' && o.kind === 'text' && editing?.id !== o.id" class="hint">Double-click to type</span>
          <span v-else-if="editing?.id !== o.id" class="text">{{ o.text }}</span>
        </div>
        <textarea
          v-if="editing?.id === o.id"
          :ref="setEditor"
          v-model="editText"
          class="editor"
          aria-label="text of the object"
          :style="editorStyle(o)"
          @keydown="onEditorKey"
          @blur="commitEdit"
          @pointerdown.stop
        />
      </div>

      <!-- what colleagues have selected: their colour and name -->
      <template v-for="other in others" :key="`${other.user}:${other.id}`">
        <div
          v-if="state.objects[other.id]"
          class="other"
          :style="{ ...boxStyle(state.objects[other.id]!), borderColor: colorOf(state, other.user) }"
          :title="other.locked ? `${other.user} is working on this` : `${other.user} selected this`"
        >
          <span class="tag" :style="{ background: colorOf(state, other.user), color: inkOn(colorOf(state, other.user)) }">{{ other.user }}</span>
        </div>
      </template>

      <!-- my selection and its handles -->
      <div v-if="selected && selectedFrame" class="mine" :style="{ left: px(selectedFrame.x), top: px(selectedFrame.y), width: px(selectedFrame.w), height: px(selectedFrame.h) }">
        <span
          v-for="h in handles"
          :key="h"
          class="handle"
          :data-handle="h"
          :style="handleStyle(h)"
          @pointerdown="onHandleDown($event, h)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.area {
  display: grid;
  place-items: center;
  overflow: hidden;
  background: color-mix(in srgb, var(--ink) 6%, var(--paper));
  outline: none;
  min-width: 0;
  min-height: 0;
  touch-action: none;
}
.slide {
  position: relative;
  background: #fff;
  box-shadow: var(--shadow);
  overflow: hidden;
  user-select: none;
}
.obj {
  position: absolute;
  cursor: default;
}
.obj.selected {
  cursor: move;
}
.obj.text.empty:not(.selected) {
  outline: 1px dashed var(--line);
}
.obj.text:hover {
  outline: 1px dashed var(--line);
}
.shape {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}
.words {
  position: absolute;
  overflow: hidden;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  pointer-events: none;
}
.hint {
  color: var(--muted);
  font-style: italic;
  font-size: 0.7em;
}
.editor {
  position: absolute;
  resize: none;
  border: none;
  outline: 2px solid var(--iris);
  background: rgb(255 255 255 / 85%);
  margin: 0;
  padding: 0;
  overflow: hidden;
  pointer-events: auto;
}
.mine {
  position: absolute;
  outline: 2px solid var(--iris);
  pointer-events: none;
}
.handle {
  position: absolute;
  width: 11px;
  height: 11px;
  margin: -6px 0 0 -6px;
  background: #fff;
  border: 2px solid var(--iris);
  border-radius: 3px;
  pointer-events: auto;
}
.other {
  position: absolute;
  border: 2px solid;
  pointer-events: none;
}
.tag {
  position: absolute;
  top: -20px;
  left: -2px;
  font-size: 11px;
  font-weight: 500;
  padding: 1px 7px;
  border-radius: 999px;
  white-space: nowrap;
}
</style>
