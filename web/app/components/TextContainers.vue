<script setup lang="ts">
// The rendered containers of a text, floating over their paragraphs (D179, D560): drawn here, in a layer of their own
// over the page, so that the editing of the words is not touched. Click selects; double-click, Enter or F2 writes in
// it; Delete removes it; the arrow keys up and down hang it from the previous or next paragraph; the corner sizes it.
import { computed, nextTick, ref } from 'vue'
import { pointer } from '~/lib/objects'
import { descriptionOf } from '~/lib/text-container-names'
import { imageDataUrl } from '~/lib/images'
import { renderedView } from '~/lib/rendering'
import { floatBox, neighbour, resizedBy } from '~/lib/text-containers'
import { useI18n } from '~/lib/i18n'
import type { TextSession } from '~/lib/text-session'

const props = defineProps<{ session: TextSession; host: HTMLElement | null; tick: number }>()
const emit = defineEmits<{ leave: [] }>()
const { t } = useI18n()
const session = props.session
const state = session.state

const layer = ref<HTMLElement | null>(null)
const editing = ref<string | null>(null)
const sizing = ref<{ id: string; from: { x: number; y: number }; w: number; h: number; now: { w: number; h: number } } | null>(null)
const readonly = computed(() => state.me.role === 'viewer')

interface Placed {
  id: string
  style: Record<string, string>
}
const placed = computed<Placed[]>(() => {
  void props.tick
  const box = layer.value?.getBoundingClientRect()
  const host = props.host
  if (!box || !host) return []
  const out: Placed[] = []
  for (const o of Object.values(state.objects)) {
    if (o.kind !== 'rendered') continue
    const paragraph = host.querySelector(`[data-block="${CSS.escape(o.anchor.container)}"]`)
    if (!paragraph) continue
    const r = paragraph.getBoundingClientRect()
    const size = sizing.value?.id === o.id ? sizing.value.now : { w: o.w, h: o.h }
    const f = floatBox(box, { left: r.left, top: r.top, width: r.width, height: r.height }, size.w, size.h)
    out.push({ id: o.id, style: { left: `${f.left}px`, top: `${f.top}px`, width: `${f.width}px`, height: `${f.height}px` } })
  }
  return out
})

const faceOf = (id: string) => {
  const o = state.objects[id]
  return o ? renderedView(state, o, imageDataUrl) : null
}
const label = (id: string) => {
  const o = state.objects[id]
  const face = faceOf(id)
  return o ? descriptionOf(o, face?.label ?? '', t) : ''
}

function select(id: string, event?: Event) {
  event?.stopPropagation()
  session.selectObject(id)
  nextTick(() => (layer.value?.querySelector(`[data-object="${CSS.escape(id)}"]`) as HTMLElement | null)?.focus({ preventScroll: true }))
}

function beginEdit(id: string) {
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
  <div ref="layer" class="layer" data-testid="containers">
    <div
      v-for="p in placed"
      :key="p.id"
      class="object"
      :class="{ selected: p.id === state.selectedObject }"
      :style="p.style"
      :data-object="p.id"
      role="button"
      tabindex="0"
      :aria-label="label(p.id)"
      @pointerdown="select(p.id, $event)"
      @dblclick.stop="beginEdit(p.id)"
      @keydown="onKey($event, p.id)"
    >
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
  pointer-events: none;
}
.object {
  position: absolute;
  pointer-events: auto;
  background: var(--paper);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  cursor: default;
}
.object.selected {
  outline: 2px solid var(--iris);
}
.object:focus-visible {
  outline: 3px solid var(--iris);
  outline-offset: 2px;
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
