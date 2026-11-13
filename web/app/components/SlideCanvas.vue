<script setup lang="ts">
// The slide on screen: its objects, and what people do to them. A click selects (and holds) an object, dragging moves
// it, the handles resize it, a double click or Enter edits its text, Delete removes it, and a right click offers the
// same "Edit text"/"Delete" at the point clicked rather than letting the browser's own menu show through. Nothing is
// believed until the server says so: while the pointer is down the frame is a preview here, committed on pointer up.
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { cutSelection, copySelection } from '~/lib/clipboard'
import { CORNERS, GRID_SIZE, HANDLES, SLIDE_H, SLIDE_W, besideRect, fitScale, moveFrame, resizeFrame, toSlide, type Frame, type Handle } from '~/lib/geometry'
import { imageDataUrl } from '~/lib/images'
import { cssOf as computedCss, slideFrame, wordsCssOf, wordsOf } from '~/lib/objects'
import { contextMenuItems } from '~/lib/object-menu'
import { objectStyleHost } from '~/lib/object-style-host'
import { colorOf, inkOn } from '~/lib/people'
import { facetCss, scaleCss } from '~/lib/slide-style'
import { withDisplayInk } from '~/lib/style-css'
import type { SlideObject, SlideSession } from '~/lib/slide-session'
import type { MenuItem } from './MenuBar.vue'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

// `showGrid` is the View menu's own preference (`lib/grid.ts`'s `useGrid`, held by SlideWorkspace.vue so the
// menu item and this canvas share the one choice) — whether the lines are drawn. It never gates snapping: an
// object snaps or not by its own `snap` field, grid lines shown or not (E10.15).
const props = defineProps<{ session: SlideSession; showGrid: boolean }>()
/** `styles` asks the workspace to open the all-styles dialog, which owns the modal layer. */
const emit = defineEmits<{ styles: [] }>()
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

/** The grid lines, drawn with a CSS background rather than one element per line; absent entirely when hidden,
 * so the slide prints and exports (D123, once that exists) exactly as it is without it. */
const gridStyle = computed(() => (props.showGrid ? { backgroundSize: `${px(GRID_SIZE)} ${px(GRID_SIZE)}` } : {}))

/** Where an object is on the screen; a frame being dragged replaces the one the server knows. */
function frameOf(o: SlideObject): Frame {
  return drag.value?.id === o.id ? drag.value.frame : slideFrame(o)
}
function boxStyle(o: SlideObject) {
  const f = frameOf(o)
  return { left: px(f.x), top: px(f.y), width: px(f.w), height: px(f.h) }
}
function cssOf(o: SlideObject) {
  // withDisplayInk: a text object's default ink, genuinely black in the document (D28/2026-11-06), still needs to
  // read against a dark slide canvas in dark mode — display-only, same fix as composes' paragraphCss.
  return withDisplayInk(scaleCss(computedCss(state.styles, o), scale.value))
}
/** The look of an object's words: its paragraph's style, not the object's own (D304, D310). */
function wordsCss(o: SlideObject) {
  return withDisplayInk(scaleCss(wordsCssOf(state.styles, o), scale.value))
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
/** Each slot draws only the facets it reads (D304), by the server's own table (`style_model`): the words their
 * text and paragraph, a text box's box its box, a shape's outline its paint. */
const facets = computed(() => state.styleModel?.facets)
function words(o: SlideObject): Record<string, string> {
  return facetCss(wordsCss(o), facets.value, ['text', 'paragraph'])
}
/** A text box's box — background, padding, a border per side (D310); a shape's box is its outline instead. */
function frameCss(o: SlideObject): Record<string, string> {
  return o.kind === 'text' ? { ...facetCss(cssOf(o), facets.value, ['box']), 'box-sizing': 'border-box' } : {}
}
function paintCss(o: SlideObject): Record<string, string> {
  return facetCss(cssOf(o), facets.value, ['outline'])
}
function textStyle(o: SlideObject): Record<string, string> {
  const centered = o.kind === 'shape'
  return { ...words(o), ...frameCss(o), display: 'flex', 'flex-direction': 'column', 'justify-content': centered ? 'center' : 'flex-start', ...textBox(o) }
}
function editorStyle(o: SlideObject): Record<string, string> {
  return { ...words(o), ...frameCss(o), ...textBox(o) }
}
function pictureOf(o: SlideObject) {
  return o.image ? (state.images[o.image] ?? null) : null
}
/** The `<img>` source for an image object's picture, or '' before the asset has loaded (`images`/`objects`'s own
 * event may arrive in either order on first load). */
function pictureSrc(o: SlideObject): string {
  const asset = pictureOf(o)
  return asset ? imageDataUrl(asset) : ''
}
const label = (o: SlideObject) => {
  if (o.kind === 'image') return t('Picture: {alt}', { alt: o.imported?.alt ?? '' })
  const kind = o.kind === 'text' ? t('Text box') : (outline(o)?.name ?? t('Shape'))
  return wordsOf(o) ? t('{kind}: {words}', { kind, words: wordsOf(o) }) : kind
}

// ------------------------------------------------------------------------------ selection, dragging, resizing
type Drag = { id: string; handle: Handle | 'move'; from: { x: number; y: number }; start: Frame; frame: Frame; moved: boolean }
const drag = ref<Drag | null>(null)

const selected = computed(() => (state.selected ? (state.objects[state.selected] ?? null) : null))
const selectedFrame = computed(() => (selected.value ? frameOf(selected.value) : null))
/** An image always keeps its own proportions, the same way a shape with a fixed `aspect` does (the server
 * refuses a `resize_object` that would not keep it, `claudia_creates._check_visual`). */
function aspectOf(o: SlideObject): number | null {
  if (o.kind === 'image') {
    const asset = pictureOf(o)
    return asset ? asset.width / asset.height : null
  }
  return outline(o)?.aspect ?? null
}
const handles = computed<Handle[]>(() => {
  const o = selected.value
  if (!o || readonly.value || editing.value) return []
  return aspectOf(o) !== null ? CORNERS : HANDLES
})

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
  drag.value = { id: o.id, handle: 'move', from: where, start: slideFrame(o), frame: slideFrame(o), moved: false }
  session.select(o.id)
}

function onHandleDown(event: PointerEvent, handle: Handle) {
  const o = selected.value
  if (!o || event.button !== 0) return
  event.stopPropagation()
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  drag.value = { id: o.id, handle, from: point(event), start: slideFrame(o), frame: slideFrame(o), moved: false }
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
  const grid = o.snap ? GRID_SIZE : null
  d.frame = d.handle === 'move' ? moveFrame(d.start, dx, dy, grid) : resizeFrame(d.start, d.handle, dx, dy, aspectOf(o), grid)
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

// ------------------------------------------------------------------------------ right-click context menu
/** The object a right click opened the menu for, and where — not necessarily `selected`'s object once a second
 * right click lands on a different one while the first's menu is still fading, so this is tracked on its own. */
const contextMenu = ref<{ x: number; y: number; id: string } | null>(null)
const contextItems = computed<MenuItem[]>(() => {
  const o = contextMenu.value ? state.objects[contextMenu.value.id] : null
  return o
    ? contextMenuItems(o, readonly.value, {
        edit: () => beginEdit(o.id),
        remove: () => session.remove(o.id),
        cut: () => cutSelection(),
        copy: () => copySelection(),
        properties: () => {
          contextMenu.value = null
          propertiesFor.value = o.id
        },
        setSnap: (snap) => session.setSnap(o.id, snap),
        style: () => {
          const at = contextMenu.value
          contextMenu.value = null
          styleMenu.value = at ? { x: at.x, y: at.y } : { x: 120, y: 160 }
        },
      })
    : []
})

// ------------------------------------------------------------------------------ the style menu (E9.7, D203)
/** Where the style menu is open, if it is. The menu itself is the one every app uses; what it styles is whatever
 * `objectStyleHost` says is selected, so this component only has to say where to put it. */
const styleMenu = ref<{ x: number; y: number; mode?: 'edit' | 'apply' } | null>(null)
const styleHost = objectStyleHost({
  get readOnly() {
    return session.readOnly
  },
  get styles() {
    return session.styleViews()
  },
  get roles() {
    return state.palette?.roles ?? []
  },
  get readings() {
    return state.palette?.readings ?? []
  },
  get selected() {
    return state.selected ? state.objects[state.selected] ?? null : null
  },
  get model() {
    return state.styleModel
  },
  get bodies() {
    return session.bodies()
  },
  applyStyle: (targets, style, slot) => session.applyStyle(targets, style, slot),
  changeStyle: (style, edit) => session.changeStyle(style, edit),
  deviateStyle: (parent, targets, slot, edit) => session.deviateStyle(parent, targets, slot, edit),
  renameStyle: (style, name) => session.renameStyle(style, name),
  checkCss: (text) => session.checkCss(text),
  setRole: (role, colour) => session.setRole(role, colour),
})

/** Format ▸ Edit this style…, Apply style… and Shift+F10: beside the selected object, so it stays in view. */
function openStyleMenu(at?: { x: number; y: number }, mode: 'edit' | 'apply' = 'edit') {
  if (!state.selected) return
  const el = area.value?.querySelector(`[data-id="${CSS.escape(state.selected)}"]`)
  const where = at ?? (el ? besideRect(el.getBoundingClientRect(), mode === 'apply' ? 280 : 360, window.innerWidth) : { x: 120, y: 160 })
  styleMenu.value = { ...where, mode }
}
function closeContextMenu() {
  contextMenu.value = null
}

// ------------------------------------------------------------------------------ image properties dialog
/** The image a right-click's "Properties" opened the dialog for (follow-up, 2026-11-07) — tracked separately from
 * `contextMenu`/`selected` since the menu itself has already closed by the time the dialog is showing. */
const propertiesFor = ref<string | null>(null)
const propertiesObject = computed(() => (propertiesFor.value ? state.objects[propertiesFor.value] ?? null : null))
/** Was showing the browser's own menu here (Back, Inspect, …) over a shape, a text box or a picture — the bug
 * this fixes. Shift + right button still gets the browser's own menu, the same escape hatch `TextEditor.vue`'s
 * `onContextMenu` already gives composes, and editing text keeps its own menu too (spelling, …), same as before. */
function onObjectContext(event: MouseEvent, o: SlideObject) {
  if (event.shiftKey || editing.value?.id === o.id) return
  event.preventDefault()
  session.select(o.id)
  contextMenu.value = { x: event.clientX, y: event.clientY, id: o.id }
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
  if (!o || editing.value || o.kind === 'image') return // a picture has no text to write
  if (readonly.value) return session.notice(t('You can only look at this document.'), 'warning')
  await session.select(o.id)
  if (state.selected !== o.id) return // a colleague holds it
  editing.value = { id: o.id, text: wordsOf(o) }
  await nextTick()
  editor.value?.focus()
  const length = wordsOf(o).length
  editor.value?.setSelectionRange(length, length)
}

async function commitEdit() {
  const e = editing.value
  if (!e) return
  editing.value = null
  area.value?.focus({ preventScroll: true })
  const current = state.objects[e.id]
  if (current && e.text !== wordsOf(current)) await session.setText(e.id, e.text)
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
    const f = moveFrame(slideFrame(o), arrow[0] * step, arrow[1] * step)
    if (f.x !== o.anchor.x || f.y !== o.anchor.y) await session.move(o.id, f.x, f.y)
  }
}

defineExpose({ focus: () => area.value?.focus(), beginEdit, openStyleMenu })

const HANDLE_CURSOR: Record<Handle, string> = { nw: 'nwse-resize', se: 'nwse-resize', ne: 'nesw-resize', sw: 'nesw-resize', n: 'ns-resize', s: 'ns-resize', e: 'ew-resize', w: 'ew-resize' }
const HANDLE_AT: Record<Handle, [number, number]> = { nw: [0, 0], n: [0.5, 0], ne: [1, 0], e: [1, 0.5], se: [1, 1], s: [0.5, 1], sw: [0, 1], w: [0, 0.5] }
const handleStyle = (h: Handle) => ({ left: `${HANDLE_AT[h][0] * 100}%`, top: `${HANDLE_AT[h][1] * 100}%`, cursor: HANDLE_CURSOR[h] })
</script>

<template>
  <div
    ref="area"
    class="area"
    tabindex="0"
    :aria-label="t('slide')"
    @keydown="onKey"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
  >
    <div
      ref="slideEl"
      class="slide"
      :class="{ grid: props.showGrid }"
      data-testid="slide"
      :data-slide="state.activeSlide"
      :style="{ width: px(SLIDE_W), height: px(SLIDE_H), ...gridStyle }"
      @pointerdown="onSlideDown"
    >
      <div
        v-for="o in objects"
        :key="o.id"
        class="obj"
        :class="[o.kind, { selected: o.id === state.selected, empty: wordsOf(o) === '' }]"
        :style="boxStyle(o)"
        :data-id="o.id"
        :aria-label="label(o)"
        role="button"
        @pointerdown="onObjectDown($event, o)"
        @dblclick.stop="beginEdit(o.id)"
        @contextmenu="onObjectContext($event, o)"
      >
        <img v-if="o.kind === 'image'" class="picture" :src="pictureSrc(o)" alt="" draggable="false" >
        <template v-else>
          <svg v-if="outline(o)" class="shape" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <path :d="outline(o)!.path" vector-effect="non-scaling-stroke" :style="paintCss(o)" />
          </svg>
          <div class="words" :style="textStyle(o)">
            <span v-if="wordsOf(o) === '' && o.kind === 'text' && editing?.id !== o.id" class="hint">{{ t('Double-click to type') }}</span>
            <span v-else-if="editing?.id !== o.id" class="text">{{ wordsOf(o) }}</span>
          </div>
          <textarea
            v-if="editing?.id === o.id"
            :ref="setEditor"
            v-model="editText"
            class="editor"
            :aria-label="t('text of the object')"
            :style="editorStyle(o)"
            @keydown="onEditorKey"
            @blur="commitEdit"
            @pointerdown.stop
          />
        </template>
      </div>

      <!-- what colleagues have selected: their colour and name -->
      <template v-for="other in others" :key="`${other.user}:${other.id}`">
        <div
          v-if="state.objects[other.id]"
          class="other"
          :style="{ ...boxStyle(state.objects[other.id]!), borderColor: colorOf(state, other.user) }"
          :title="other.locked ? t('{user} is working on this', { user: other.user }) : t('{user} selected this', { user: other.user })"
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

    <ContextMenu v-if="contextMenu" :x="contextMenu.x" :y="contextMenu.y" :items="contextItems" :label="t('Object menu')" @close="closeContextMenu" />
    <StyleMenu v-if="styleMenu" :host="styleHost" :x="styleMenu.x" :y="styleMenu.y" :mode="styleMenu.mode" @close="styleMenu = null" @styles="((styleMenu = null), emit('styles'))" />
    <ImagePropertiesDialog v-if="propertiesObject" :session="session" :object="propertiesObject" @close="propertiesFor = null" />
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
.slide.grid {
  /* E10.15: a helper the view draws, never part of the slide itself — background-position/-size only, so it
   * never shows up in anything that exports or prints the slide's own content. */
  background-image: linear-gradient(to right, var(--grid) 1px, transparent 1px), linear-gradient(to bottom, var(--grid) 1px, transparent 1px);
  background-position: -1px -1px;
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
.picture {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
  user-select: none;
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
