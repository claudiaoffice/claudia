<script setup lang="ts">
// A presentation: the slide, the tool bar to put things on it, the slides along the bottom and the panel.
import { computed, ref } from 'vue'
import { insertFrame } from '~/lib/geometry'
import type { SlideSession } from '~/lib/slide-session'
import DocumentFrame from './DocumentFrame.vue'
import SlideCanvas from './SlideCanvas.vue'
import type { Menu } from './MenuBar.vue'

const props = defineProps<{ session: SlideSession }>()
const emit = defineEmits<{ leave: [] }>()

const session = props.session
const state = session.state
const frame = ref<InstanceType<typeof DocumentFrame> | null>(null)
const canvas = ref<InstanceType<typeof SlideCanvas> | null>(null)
const help = ref(false)

const readonly = computed(() => state.me.role === 'viewer')
const here = computed(() => state.slides.findIndex((s) => s.id === state.activeSlide))
const count = computed(() => session.objectsOn(state.activeSlide).length)

async function addText() {
  if (await session.addText(insertFrame('text', null, count.value))) canvas.value?.focus()
}
async function addShape(id: string) {
  const outline = state.library.find((s) => s.id === id) ?? state.shapes[id]
  if (await session.addShape(id, insertFrame('shape', outline?.aspect ?? null, count.value))) canvas.value?.focus()
}
async function remove() {
  if (state.selected) await session.remove(state.selected)
  canvas.value?.focus()
}

const menus = computed<Menu[]>(() => [
  {
    label: 'File',
    items: [
      { label: 'New slide', action: () => session.addSlide(), disabled: readonly.value },
      { label: '', separator: true },
      { label: 'Save', hint: 'Ctrl+S', action: () => frame.value?.checkpoint(null), disabled: readonly.value },
      { label: 'Save with a name…', action: () => frame.value?.openDialog('checkpoint'), disabled: readonly.value },
      { label: '', separator: true },
      { label: 'Share…', action: () => frame.value?.openDialog('share'), disabled: state.me.role !== 'owner' },
      { label: '', separator: true },
      { label: 'Close document', action: () => emit('leave') },
    ],
  },
  {
    label: 'Edit',
    items: [
      { label: state.canUndo ? `Undo ${state.undoLabel}` : 'Undo', hint: 'Ctrl+Z', action: () => session.undo(), disabled: !state.canUndo },
      { label: state.canRedo ? `Redo ${state.redoLabel}` : 'Redo', hint: 'Ctrl+Y', action: () => session.redo(), disabled: !state.canRedo },
      { label: '', separator: true },
      { label: 'Edit text', hint: 'Enter', action: () => canvas.value?.beginEdit(), disabled: readonly.value || !state.selected },
      { label: 'Delete', hint: 'Del', action: () => remove(), disabled: readonly.value || !state.selected },
    ],
  },
  {
    label: 'Insert',
    items: [
      { label: 'Text box', action: () => addText(), disabled: readonly.value },
      { label: '', separator: true },
      ...state.library.map((s) => ({ label: s.name, action: () => addShape(s.id), disabled: readonly.value })),
    ],
  },
  { label: 'Tools', items: [{ label: 'Ask the assistant…', action: () => frame.value?.ask('@ai ') }] },
  { label: 'Help', items: [{ label: 'Keyboard', action: () => (help.value = true) }] },
])
</script>

<template>
  <DocumentFrame ref="frame" :session="session" :menus="menus" @leave="emit('leave')" @saved="canvas?.focus()">
    <template #toolbar>
      <InsertBar
        :shapes="state.library"
        :can-delete="state.selected !== null"
        :can-undo="state.canUndo"
        :can-redo="state.canRedo"
        :undo-label="state.undoLabel"
        :redo-label="state.redoLabel"
        :readonly="readonly"
        @text="addText"
        @shape="addShape"
        @remove="remove"
        @undo="session.undo()"
        @redo="session.redo()"
      />
    </template>
    <SlideCanvas v-if="state.activeSlide" ref="canvas" :session="session" />
    <div v-else class="noslide">This presentation has no slide.</div>
    <template #footer>
      <footer class="foot">
        <div class="tabs" role="tablist" aria-label="slides">
          <button
            v-for="(s, i) in state.slides"
            :key="s.id"
            type="button"
            role="tab"
            :aria-selected="s.id === state.activeSlide"
            :class="{ on: s.id === state.activeSlide }"
            @click="session.showSlide(s.id)"
          >
            Slide {{ i + 1 }}
          </button>
          <button v-if="!readonly" type="button" class="add" title="New slide" aria-label="new slide" @click="session.addSlide()">+</button>
        </div>
        <div class="stats mono">
          <span v-if="here >= 0">{{ here + 1 }} / {{ state.slides.length }}</span>
          <span class="rev" :title="`line ${state.line}`">{{ state.revision ?? 'empty' }}</span>
        </div>
      </footer>
    </template>
    <template #overlay>
      <Modal v-if="help" title="Keyboard" @close="help = false">
        <dl class="keys">
          <dt>Click</dt><dd>select an object (colleagues cannot change it while you hold it)</dd>
          <dt>Drag</dt><dd>move it; the handles resize it</dd>
          <dt>Double-click, Enter</dt><dd>write in it; Enter keeps the text, Shift+Enter starts a line, Esc drops it</dd>
          <dt>Arrows</dt><dd>move it by 10 units; with Shift by 1</dd>
          <dt>Delete</dt><dd>take it off the slide</dd>
          <dt>Esc</dt><dd>select nothing</dd>
          <dt>Ctrl+Z, Ctrl+Y</dt><dd>undo and redo your own steps</dd>
        </dl>
        <button class="btn primary" type="button" @click="help = false">Close</button>
      </Modal>
    </template>
  </DocumentFrame>
</template>

<style scoped>
.noslide {
  display: grid;
  place-items: center;
  color: var(--muted);
}
.foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  height: 36px;
  padding: 0 10px;
  background: var(--surface);
  border-top: 1px solid var(--line);
}
.tabs {
  display: flex;
  gap: 4px;
  overflow-x: auto;
}
.tabs button {
  border: 0;
  background: transparent;
  padding: 4px 14px;
  border-radius: 8px;
  white-space: nowrap;
}
.tabs button:hover {
  background: var(--mist);
}
.tabs button.on {
  background: var(--app-soft);
  color: var(--app-dark);
  font-weight: 500;
  box-shadow: inset 0 -2px 0 var(--app);
  border-radius: 8px 8px 0 0;
}
.add {
  font-size: 18px;
  line-height: 1;
  padding: 3px 11px !important;
  color: var(--muted);
}
.stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
}
.rev {
  opacity: 0.8;
}
.keys {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 18px;
  margin: 0;
}
.keys dt {
  font-weight: 500;
}
.keys dd {
  margin: 0;
  color: var(--muted);
}
</style>
