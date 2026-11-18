<script setup lang="ts">
// The floating objects of a text, over their characters (D179, D560, E10.16): drawn here, in a layer of their own over
// the page, so that the editing of the words is not touched. An object hangs at the character it is anchored to, moved
// by the offset the model keeps (`floatBox`), which is where it is printed too. A rendered container, a picture, a
// shape and a text box are all drawn (`lookOf`). A table is not drawn here: it is in the flow and `TableView.vue` is its
// only body (D1201). Click selects (and a click into the words lets go again, in `TextEditor.vue`); dragging moves the
// object, to where it is dropped (the paragraph nearest and the offset left over, D1023); the handles size it and the
// handle above turns it (`ObjectFrame.vue`, the same in all three apps, D1221); the right button selects it and opens its
// menu (D1225); double-click, Enter or F2 writes in a rendered container; Delete removes an object; the arrow keys up and
// down hang it from the previous or next paragraph; Esc drops what is being tried.
//
// Two of these layers stand in a text (D1063): the one over the words, and one under them for the objects whose
// text wrap is "behind the text". The words are drawn above that one, so a press there goes to the words; while Ctrl
// is held, the layer comes up over the words and takes the press, and the pointer shows a hand (`grabbable`).
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { pointer, type BlockAnchor } from '~/lib/objects'
import { descriptionOf } from '~/lib/text-container-names'
import { objectName } from '~/lib/descriptions'
import { imageDataUrl } from '~/lib/images'
import { renderedView } from '~/lib/rendering'
import { columnOf, floatBox, neighbour } from '~/lib/text-containers'
import type { Frame, Handle } from '~/lib/geometry'
import { CORNERS, HANDLES } from '~/lib/geometry'
import { useObjectInteraction } from '~/lib/object-interaction'
import { canTurn, degreesText, stepTurn } from '~/lib/turning'
import { stepsFor, type Place, type Spot } from '~/lib/text-object-host'
import { lookOf, type ObjectLook } from '~/lib/text-object-look'
import { useI18n } from '~/lib/i18n'
import type { TextSession } from '~/lib/text-session'
import { grabbable, wrapLabel, wrapOf } from '~/lib/wrap'

const props = defineProps<{
  session: TextSession
  host: HTMLElement | null
  /** The layer under the words, for the objects that lie behind them; absent: the one over the words. */
  behind?: boolean
  tick: number
  /** Where, on the screen, the character at a place of the text is (`TextEditor.vue`'s `spotOf`). */
  spotOf: (place: Place) => Spot | null
  /** The place of the text nearest a point of the screen (`TextEditor.vue`'s `placeAt`): where a dropped object hangs. */
  placeAt: (x: number, y: number) => Place | null
  /** A turn being tried from Rotate By…, drawn but not sent until Done. */
  turning?: { id: string; turn: number } | null
}>()
const emit = defineEmits<{ leave: []; menu: [at: { id: string; x: number; y: number }] }>()
const { t } = useI18n()
const session = props.session
const state = session.state

const layer = ref<HTMLElement | null>(null)
/** The container being written in: in the state, so that the object menu's Edit text can start it too. */
const editing = computed({
  get: () => state.editingObject,
  set: (id: string | null) => (state.editingObject = id),
})
/** What a screen reader is told after a turn. */
const turnSaid = ref('')
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

/** Where an object is, on the layer: its box (`floatBox`), the place it hangs from and that place's spot on the screen. */
interface Geometry {
  frame: Frame
  place: Place
  spot: Spot
  layer: DOMRect
}
function geometryOf(o: (typeof state.objects)[string]): Geometry | null {
  const layerBox = layer.value?.getBoundingClientRect()
  const host = props.host
  if (!layerBox || !host) return null
  const place = session.placeOf(o)
  const spot = place && props.spotOf(place)
  if (!place || !spot) return null
  const r = host.getBoundingClientRect()
  const css = getComputedStyle(host)
  const column = columnOf({ left: r.left, top: r.top, width: r.width, height: r.height }, parseFloat(css.paddingLeft) || 0, parseFloat(css.paddingRight) || 0)
  const f = floatBox(layerBox, spot, o.anchor, o.w, o.h, column)
  return { frame: { x: f.left, y: f.top, w: f.width, h: f.height }, place, spot, layer: layerBox }
}

/** The angle an object is drawn at: the turn being tried by the handle or by Rotate By…, else its own. */
function rotationOf(id: string): number {
  const o = state.objects[id]
  if (props.turning?.id === id) return props.turning.turn
  return interaction.rotationOf(id) ?? o?.rotation ?? 0
}
/** A picture and a shape with a fixed aspect keep their proportions when sized (the server refuses anything else, so
 * the screen must not offer it); a container and a text box are free. */
function aspectOf(id: string): number | null {
  const o = state.objects[id]
  if (!o) return null
  if (o.kind === 'image') {
    const asset = pointer(o, 'image') ? state.images[pointer(o, 'image')!] : null
    return asset ? asset.width / asset.height : null
  }
  const shape = pointer(o, 'shape')
  return (shape ? state.shapes[shape]?.aspect : null) ?? null
}

/** What the interaction needs of composes (`object-interaction.ts`): its area is the layer, in screen pixels, and an
 * object's frame is where `floatBox` puts it; a release becomes server steps (`text-object-host.ts`). */
const interaction = useObjectInteraction({
  get bounds() {
    const r = layer.value?.getBoundingClientRect()
    return { w: r?.width ?? 0, h: r?.height ?? 0 }
  },
  scale: 1,
  get readonly() {
    return readonly.value
  },
  toUnits(event) {
    const r = layer.value!.getBoundingClientRect()
    return { x: event.clientX - r.left, y: event.clientY - r.top }
  },
  subject(id) {
    const o = state.objects[id]
    const g = o && geometryOf(o)
    return o && g ? { id, frame: g.frame, rotation: o.rotation, aspect: aspectOf(id), grid: null } : null
  },
  async commit(change) {
    const o = state.objects[change.id]
    const g = o && geometryOf(o)
    if (!o || !g) return false
    let dropped: { place: Place; spot: Spot } | null = null
    if (change.kind === 'move') {
      // the object hangs from the place nearest where its top left corner was dropped (a point inside it, not on its edge)
      const at = props.placeAt(g.layer.left + change.x + 1, g.layer.top + change.y + 1)
      const spot = at && (at.block !== g.place.block || at.offset !== g.place.offset) ? props.spotOf(at) : null
      if (at && spot) dropped = { place: at, spot }
    }
    for (const step of stepsFor(change, { layer: g.layer, start: g.frame, current: { place: g.place, spot: g.spot }, dropped })) {
      const ok =
        step.kind === 'move' ? await session.moveObject(o.id, step.place, step.away) : step.kind === 'resize' ? await session.resizeObject(o.id, step.w, step.h) : await session.rotateObject(o.id, step.rotation)
      if (!ok) return false
    }
    return true
  },
})

interface Placed {
  id: string
  style: Record<string, string>
  frame: Frame
}
const placed = computed<Placed[]>(() => {
  void props.tick
  if (!layer.value || !props.host) return []
  const out: Placed[] = []
  for (const o of Object.values(state.objects)) {
    if (o.kind === 'table' || !mine(o.id)) continue // a table is in the flow: `TableView.vue` draws it
    const g = geometryOf(o)
    if (!g) continue
    const f = interaction.frameOf(o.id) ?? g.frame
    const turned = rotationOf(o.id)
    const turn: Record<string, string> = turned ? { transform: `rotate(${turned}deg)` } : {}
    out.push({ id: o.id, frame: f, style: { left: `${f.x}px`, top: `${f.y}px`, width: `${f.w}px`, height: `${f.h}px`, ...turn } })
  }
  return out
})

const faceOf = (id: string) => {
  const o = state.objects[id]
  return o ? renderedView(state, o, imageDataUrl) : null
}
const looks = computed<Record<string, ObjectLook>>(() => Object.fromEntries(Object.values(state.objects).filter((o) => o.kind !== 'table').map((o) => [o.id, lookOf(state, o)])))
const label = (id: string) => {
  const o = state.objects[id]
  if (!o) return ''
  const name =
    o.kind === 'rendered'
      ? descriptionOf(o, faceOf(id)?.label ?? '', t)
      : objectName(o, { shape: pointer(o, 'shape') ? state.shapes[pointer(o, 'shape')!]?.name : undefined, words: o.paragraph?.text })
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
  const object = state.objects[id]
  const rendering = object ? pointer(object, 'rendered') : null
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
    if (interaction.cancel()) return // what was being tried is dropped, the object is as it was
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

// ------------------------------------------------------------------------------ the pointer: drag, size, turn (D1221)
/** A press on the object: it is selected, and dragging moves it. Another button only selects (the menu is its own). */
function onDown(event: PointerEvent, id: string) {
  select(id, event)
  if (event.button !== 0 || readonly.value || editing.value === id) return
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  interaction.begin(id, 'move', event)
}
function onHandle(event: PointerEvent, id: string, handle: Handle) {
  if (event.button !== 0 || readonly.value) return
  event.stopPropagation()
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  interaction.begin(id, handle, event)
}
function onTurnDown(event: PointerEvent, id: string) {
  if (event.button !== 0 || readonly.value) return
  event.stopPropagation()
  event.preventDefault() // the handle takes no focus from the mouse: the object keeps it, so Esc reaches it
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  interaction.begin(id, 'turn', event)
}
/** The arrow keys on the turn handle: a degree, Shift 15° (the handle is a slider for a screen reader). */
async function onTurnKey(event: KeyboardEvent, id: string) {
  const o = state.objects[id]
  if (!o || readonly.value) return
  const by: Record<string, number> = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }
  const to = by[event.key] !== undefined ? stepTurn(o.rotation, by[event.key]! * (event.shiftKey ? 15 : 1)) : event.key === 'Home' ? 0 : null
  if (to === null) return
  event.preventDefault()
  event.stopPropagation()
  if (to !== o.rotation && (await session.rotateObject(id, to))) turnSaid.value = t('Turned to {degrees}', { degrees: degreesText(state.objects[id]?.rotation ?? to) })
}
async function onUp() {
  const change = await interaction.release()
  if (change?.kind === 'rotate') turnSaid.value = t('Turned to {degrees}', { degrees: degreesText(change.rotation) })
}

/** The right button: the object is selected and its menu opens where it was pressed, and nothing below it (the words,
 * the paragraph menu) is reached (D1225). Shift + right button is still the browser's own menu. */
function onContext(event: MouseEvent, id: string) {
  if (event.shiftKey && event.clientX !== 0) return
  event.preventDefault()
  event.stopPropagation()
  select(id)
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const keyboard = event.clientX === 0 && event.clientY === 0
  emit('menu', { id, x: keyboard ? rect.left + rect.width / 2 : event.clientX, y: keyboard ? rect.top + rect.height / 2 : event.clientY })
}

const handlesOf = (id: string): Handle[] => (aspectOf(id) !== null ? CORNERS : HANDLES)
/** The turn handle would be above the top of the page: it goes below the object. */
const handleBelow = (p: Placed) => p.frame.y < 60
const turnable = (id: string) => !!state.objects[id] && canTurn(state.objects[id]!.kind)
</script>

<template>
  <div
    ref="layer"
    class="layer"
    :class="{ behind, grab: behind && grabbable('behind', ctrl) }"
    :data-testid="behind ? 'containers-behind' : 'containers'"
  >
    <p class="sr" role="status" aria-live="polite">{{ turnSaid }}</p>
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
      @pointerdown="onDown($event, p.id)"
      @pointermove="interaction.move($event)"
      @pointerup="onUp"
      @pointercancel="onUp"
      @contextmenu="onContext($event, p.id)"
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
      <ObjectFrame
        v-if="p.id === state.selectedObject && !readonly && !editing"
        :handles="handlesOf(p.id)"
        :turnable="turnable(p.id)"
        :turn="rotationOf(p.id)"
        :turning="interaction.turningNow(p.id)"
        :below="handleBelow(p)"
        @handle="(e, h) => onHandle(e, p.id, h)"
        @turn-down="(e) => onTurnDown(e, p.id)"
        @turn-key="(e) => onTurnKey(e, p.id)"
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
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
