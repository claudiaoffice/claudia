<script setup lang="ts">
// The floating objects of a text, over their characters (D179, D560, E10.16): drawn here, in a layer of their own over
// the page, so that the editing of the words is not touched. An object hangs at the character it is anchored to, moved
// by the offset the model keeps (`floatBox`), which is where it is printed too. A rendered container, a picture, a
// shape and a text box are all drawn (`lookOf`). Click selects (and a click into the words lets go again, in
// `TextEditor.vue`); double-click, Enter or F2 writes in a rendered container; Delete removes an object; the arrow keys
// up and down hang it from the previous or next paragraph; the corner sizes it.
//
// Two of these layers stand in a text (D1063): the one over the words, and one under them for the objects whose
// text wrap is "behind the text". The words are drawn above that one, so a press there goes to the words; while Ctrl
// is held, the layer comes up over the words and takes the press, and the pointer shows a hand (`grabbable`).
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { descriptionOf } from '~/lib/text-container-names'
import { objectName } from '~/lib/descriptions'
import { imageDataUrl } from '~/lib/images'
import { renderedView } from '~/lib/rendering'
import { columnOf, floatBox, neighbour, resizedBy } from '~/lib/text-containers'
import { lookOf, type ObjectLook } from '~/lib/text-object-look'
import { useI18n } from '~/lib/i18n'
import type { TextSession } from '~/lib/text-session'
import { grabbable, wrapLabel, wrapOf } from '~/lib/wrap'
import type { BlockAnchor } from '~/lib/objects'

const props = defineProps<{
  session: TextSession
  host: HTMLElement | null
  /** The layer under the words, for the objects that lie behind them; absent: the one over the words. */
  behind?: boolean
  tick: number
  /** Where, on the screen, the character at a place of the text is (`TextEditor.vue`'s `spotOf`). */
  spotOf: (place: { block: string; offset: number }) => { left: number; top: number } | null
}>()
const emit = defineEmits<{ leave: [] }>()
const { t } = useI18n()
const session = props.session
const state = session.state

const layer = ref<HTMLElement | null>(null)
const editing = ref<string | null>(null)
const sizing = ref<{ id: string; from: { x: number; y: number }; w: number; h: number; now: { w: number; h: number } } | null>(null)
const readonly = computed(() => state.me.role === 'viewer')

/** Is Ctrl held? Then an object behind the words can be taken hold of (D1063). */
const ctrl = ref(false)
const onModifier = (event: KeyboardEvent) => (ctrl.value = event.ctrlKey || event.metaKey)
const onBlur = () => (ctrl.value = false)
onMounted(() => {
  if (!props.behind) return
  window.addEventListener('keydown', onModifier)
  window.addEventListener('keyup', onModifier)
  window.addEventListener('blur', onBlur)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onModifier)
  window.removeEventListener('keyup', onModifier)
  window.removeEventListener('blur', onBlur)
})
/** The wrap an object says it has: only an object hung in the words has one; a slide's or a cell's is never behind. */
const wrapOfObject = (id: string) => {
  const a = state.objects[id]?.anchor as Partial<BlockAnchor> | undefined
  return a && 'container' in a ? wrapOf(a).wrap : 'over'
}
const mine = (id: string) => (wrapOfObject(id) === 'behind') === !!props.behind

interface Placed {
  id: string
  style: Record<string, string>
}
const placed = computed<Placed[]>(() => {
  void props.tick
  const box = layer.value?.getBoundingClientRect()
  const host = props.host
  if (!box || !host) return []
  const r = host.getBoundingClientRect()
  const css = getComputedStyle(host)
  const column = columnOf({ left: r.left, top: r.top, width: r.width, height: r.height }, parseFloat(css.paddingLeft) || 0, parseFloat(css.paddingRight) || 0)
  const out: Placed[] = []
  for (const o of Object.values(state.objects)) {
    if (!mine(o.id)) continue
    const place = session.placeOf(o)
    const spot = place && props.spotOf(place)
    if (!spot) continue
    const size = sizing.value?.id === o.id ? sizing.value.now : { w: o.w, h: o.h }
    const f = floatBox(box, spot, o.anchor, size.w, size.h, column)
    const turn: Record<string, string> = o.rotation ? { transform: `rotate(${o.rotation}deg)` } : {}
    out.push({ id: o.id, style: { left: `${f.left}px`, top: `${f.top}px`, width: `${f.width}px`, height: `${f.height}px`, ...turn } })
  }
  return out
})

const faceOf = (id: string) => {
  const o = state.objects[id]
  return o ? renderedView(state, o, imageDataUrl) : null
}
const looks = computed<Record<string, ObjectLook>>(() => Object.fromEntries(Object.values(state.objects).map((o) => [o.id, lookOf(state, o)])))
const label = (id: string) => {
  const o = state.objects[id]
  if (!o) return ''
  const name =
    o.kind === 'rendered'
      ? descriptionOf(o, faceOf(id)?.label ?? '', t)
      : objectName(o, { shape: o.shape ? state.shapes[o.shape]?.name : undefined, words: o.paragraph?.text })
  // a screen-reader user hears how the words go round it, where it matters (BITV 1.3.1)
  const wrap = wrapOfObject(id)
  return wrap === 'over' ? name : `${name}, ${wrapLabel(wrap)}`
}

function select(id: string, event?: Event) {
  event?.stopPropagation()
  session.selectObject(id)
  nextTick(() => (layer.value?.querySelector(`[data-object="${CSS.escape(id)}"]`) as HTMLElement | null)?.focus({ preventScroll: true }))
}

function beginEdit(id: string) {
  if (state.objects[id]?.kind !== 'rendered') return // only a rendered container is written in, here
  if (readonly.value) return session.notice(t('You can only look at this document.'), 'warning')
  select(id)
  editing.value = id
}
function done() {
  editing.value = null
  nextTick(() => (layer.value?.querySelector(`[data-object="${CSS.escape(state.selectedObject ?? '')}"]`) as HTMLElement | null)?.focus({ preventScroll: true }))
}
async function commit(id: string, text: string) {
  const rendering = state.objects[id]?.rendered
  done()
  if (rendering) await session.setRenderingSource(rendering, text)
}

async function onKey(event: KeyboardEvent, id: string) {
  if (editing.value) return
  const o = state.objects[id]
  if (!o) return
  if (event.key === 'Enter' || event.key === 'F2') {
    event.preventDefault()
    return beginEdit(id)
  }
  if (event.key === 'Escape') {
    event.preventDefault()
    session.selectObject(null)
    return emit('leave')
  }
  if (readonly.value) return
  if (event.key === 'Delete' || event.key === 'Backspace') {
    event.preventDefault()
    return void session.removeObject(id)
  }
  if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
    event.preventDefault()
    const to = neighbour(state.blocks.map((b) => b.id), o.anchor.container, event.key === 'ArrowDown' ? 1 : -1)
    if (to !== o.anchor.container) await session.moveObject(id, { block: to, offset: 0 })
  }
}

function startSizing(event: PointerEvent, id: string) {
  const o = state.objects[id]
  if (!o || readonly.value || event.button !== 0) return
  event.stopPropagation()
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  sizing.value = { id, from: { x: event.clientX, y: event.clientY }, w: o.w, h: o.h, now: { w: o.w, h: o.h } }
}
function onSizing(event: PointerEvent) {
  const d = sizing.value
  if (d) d.now = resizedBy(d.w, d.h, event.clientX - d.from.x, event.clientY - d.from.y)
}
async function endSizing() {
  const d = sizing.value
  sizing.value = null
  if (d && (d.now.w !== d.w || d.now.h !== d.h)) await session.resizeObject(d.id, d.now.w, d.now.h)
}
</script>

<template>
  <div
    ref="layer"
    class="layer"
    :class="{ behind, grab: behind && grabbable('behind', ctrl) }"
    :data-testid="behind ? 'containers-behind' : 'containers'"
  >
    <div
      v-for="p in placed"
      :key="p.id"
      class="object"
      :class="[{ selected: p.id === state.selectedObject }, `kind-${state.objects[p.id]?.kind}`]"
      :style="p.style"
      :data-object="p.id"
      role="button"
      tabindex="0"
      :aria-label="label(p.id)"
      @pointerdown="select(p.id, $event)"
      @dblclick.stop="beginEdit(p.id)"
      @keydown="onKey($event, p.id)"
    >
      <template v-if="looks[p.id]?.rendered">
        <template v-if="faceOf(p.id)">
          <RenderedEditor
            v-if="editing === p.id"
            :text="faceOf(p.id)!.definition.source"
            :label="faceOf(p.id)!.label"
            @commit="commit(p.id, $event)"
            @cancel="done"
          />
          <RenderedFace v-else :src="faceOf(p.id)!.src" :status="faceOf(p.id)!.status" :label="faceOf(p.id)!.label" />
        </template>
      </template>
      <img v-else-if="looks[p.id]?.picture" class="picture" :src="looks[p.id]!.picture" alt="" draggable="false" >
      <p v-else-if="looks[p.id]?.unsupported" class="unsupported">{{ t('A chart is not shown in a text yet.') }}</p>
      <template v-else-if="looks[p.id]">
        <svg v-if="looks[p.id]!.outline" class="shape" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path :d="looks[p.id]!.outline!.path" vector-effect="non-scaling-stroke" :style="looks[p.id]!.outline!.paint" />
        </svg>
        <div v-if="looks[p.id]!.words" class="words" :style="{ ...looks[p.id]!.words!.css, ...looks[p.id]!.words!.area }">
          <ParagraphWords :text="looks[p.id]!.words!.text" />
        </div>
      </template>
      <span
        v-if="p.id === state.selectedObject && !readonly && !editing"
        class="grip"
        :title="t('Drag to resize')"
        @pointerdown="startSizing($event, p.id)"
        @pointermove="onSizing"
        @pointerup="endSizing"
        @pointercancel="endSizing"
      />
    </div>
  </div>
</template>

<style scoped>
.layer {
  position: absolute;
  inset: 0;
  z-index: 2; /* over the words (`.doc` is 1); the layer under them is 0 */
  pointer-events: none;
}
.object {
  position: absolute;
  pointer-events: auto;
  cursor: default;
}
/* the layer under the words: the words are above it, so it takes no press, until Ctrl is held; then it comes up over
   the words, the object shows a hand, and the rest of the page still answers to the words (D1063) */
.layer.behind {
  z-index: 0;
}
.layer.behind .object {
  pointer-events: none;
}
.layer.behind.grab {
  z-index: 3;
}
.layer.behind.grab .object {
  pointer-events: auto;
  cursor: grab;
}
.layer.behind.grab .object:active {
  cursor: grabbing;
}

/* only a rendered container is a framed card; a picture, a shape and a text box bring their own look */
.object.kind-rendered {
  background: var(--paper);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
.object.selected {
  outline: 2px solid var(--iris);
}
.object:focus-visible {
  outline: 3px solid var(--iris);
  outline-offset: 2px;
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
.unsupported {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 8px;
  text-align: center;
  font-size: 0.85em;
  color: var(--muted);
  background: var(--paper);
  border: 1px dashed var(--line);
}
.grip {
  position: absolute;
  right: -6px;
  bottom: -6px;
  width: 11px;
  height: 11px;
  background: #fff;
  border: 2px solid var(--iris);
  border-radius: 3px;
  cursor: nwse-resize;
}
</style>
