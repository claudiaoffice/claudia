<script setup lang="ts">
// A presentation: the slide, the tool bar to put things on it, the slides along the bottom and the panel.
import { computed, ref } from 'vue'
import { insertFrame } from '~/lib/geometry'
import type { SlideSession } from '~/lib/slide-session'
import { copySelection, cutSelection, pasteAsPlainText } from '~/lib/clipboard'
import { useTheme } from '~/lib/theme'
import DocumentFrame from './DocumentFrame.vue'
import SlideCanvas from './SlideCanvas.vue'
import type { Menu } from './MenuBar.vue'

const props = defineProps<{ session: SlideSession }>()
const emit = defineEmits<{ leave: [opts?: { startFresh?: boolean }] }>()

const session = props.session
const state = session.state
const { dark, toggle: toggleDark } = useTheme()
const frame = ref<InstanceType<typeof DocumentFrame> | null>(null)
const canvas = ref<InstanceType<typeof SlideCanvas> | null>(null)

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

/** Copy/Cut act on whatever the browser still has selected; Paste only does anything while a text frame is in edit
 * mode (`document.activeElement` is then its contenteditable) — same honest limit `lib/clipboard.ts` documents: a
 * shape or an unselected canvas has no text to paste into, and the menu click quietly does nothing, same as a
 * native paste finding nowhere to land. */
async function pasteFromClipboard() {
  await pasteAsPlainText(document.activeElement)
}

const menus = computed<Menu[]>(() => [
  {
    label: 'File',
    items: [
      { id: 'file.new', label: 'New', action: () => emit('leave', { startFresh: true }) },
      { id: 'file.open', label: 'Open…', action: () => emit('leave') },
      { label: '', separator: true },
      { id: 'file.save', label: 'Save', hint: 'Ctrl+S', action: () => frame.value?.checkpoint(null), disabled: readonly.value },
      { id: 'file.save-as', label: 'Save new checkpoint…', action: () => frame.value?.openDialog('checkpoint'), disabled: readonly.value },
      { id: 'file.download', label: 'Download', disabled: true }, // D123: a stub here until creates has an export format
      { label: '', separator: true },
      {
        id: 'file.manage',
        label: 'Manage',
        items: [
          { id: 'file.manage.share', label: 'Share…', action: () => frame.value?.openDialog('share'), disabled: state.me.role !== 'owner' },
          {
            id: 'file.manage.assign-owner',
            label: 'Assign new owner…',
            action: () => frame.value?.openDialog('assign-owner'),
            disabled: state.me.role !== 'owner',
          },
          {
            id: 'file.manage.accept-owner',
            label: 'Accept ownership…',
            action: () => frame.value?.openDialog('accept-owner'),
            disabled: state.me.role === 'viewer',
          },
          { id: 'file.manage.leave', label: 'Leave document…', action: () => frame.value?.openDialog('leave') },
          { id: 'file.manage.export', label: 'Export…', action: () => frame.value?.openDialog('export') },
          {
            id: 'file.manage.delete',
            label: 'Delete from server…',
            action: () => frame.value?.openDialog('delete'),
            disabled: state.me.role !== 'owner',
          },
        ],
      },
      { label: '', separator: true },
      { id: 'file.close', label: 'Close document', action: () => emit('leave') },
    ],
  },
  {
    label: 'Edit',
    items: [
      { id: 'edit.undo', label: state.canUndo ? `Undo ${state.undoLabel}` : 'Undo', hint: 'Ctrl+Z', action: () => session.undo(), disabled: !state.canUndo },
      { id: 'edit.redo', label: state.canRedo ? `Redo ${state.redoLabel}` : 'Redo', hint: 'Ctrl+Shift+Z', action: () => session.redo(), disabled: !state.canRedo },
      { label: '', separator: true },
      { id: 'edit.copy', label: 'Copy', hint: 'Ctrl+C', action: () => copySelection() },
      { id: 'edit.cut', label: 'Cut', hint: 'Ctrl+X', action: () => cutSelection(), disabled: readonly.value },
      { id: 'edit.paste', label: 'Paste', hint: 'Ctrl+V', action: () => pasteFromClipboard(), disabled: readonly.value },
      {
        id: 'edit.paste-as',
        label: 'Paste as',
        disabled: readonly.value,
        // The child's own `disabled` is what a shell actually reports per-action (`collectStates` walks each item on
        // its own terms, not by inheriting a parent's); the parent's `disabled` above only keeps the web menu from
        // opening the flyout at all — both need to agree, or a shell could show the leaf as enabled regardless.
        items: [{ id: 'edit.paste-as-plain', label: 'Plain text', action: () => pasteFromClipboard(), disabled: readonly.value }],
      },
      { label: '', separator: true },
      { id: 'edit.new-slide', label: 'New slide', action: () => session.addSlide(), disabled: readonly.value },
      { label: '', separator: true },
      { id: 'edit.edit-text', label: 'Edit text', hint: 'Enter', action: () => canvas.value?.beginEdit(), disabled: readonly.value || !state.selected },
      { id: 'edit.text-box', label: 'Text box', action: () => addText(), disabled: readonly.value },
      { label: '', separator: true },
      ...state.library.map((s) => ({ label: s.name, action: () => addShape(s.id), disabled: readonly.value })),
      { label: '', separator: true },
      { id: 'edit.delete', label: 'Delete', hint: 'Del', action: () => remove(), disabled: readonly.value || !state.selected },
    ],
  },
  { label: 'Format', items: [{ id: 'format.none', label: 'No styles yet', disabled: true }] }, // D125: visible, inert — creates has no style system yet
  {
    label: 'View',
    items: [
      { id: 'view.authors', label: 'Show who wrote what', checked: false, disabled: true }, // creates tracks no per-object authorship yet
      {
        id: 'view.panel',
        label: 'History and chat',
        checked: frame.value?.isPanelOpen() ?? true,
        action: (t) => {
          const open = frame.value?.isPanelOpen() ?? true
          if (t === undefined || (t === 'on') !== open) frame.value?.togglePanel()
        },
      },
      {
        id: 'view.dark',
        label: 'Dark mode',
        checked: dark(),
        action: (t) => {
          if (t === undefined || (t === 'on') !== dark()) toggleDark()
        },
      },
    ],
  },
  { label: 'Tools', items: [{ id: 'tools.ask', label: 'Ask the assistant…', action: () => frame.value?.ask('@ai ') }] },
  { label: 'Config', items: [{ id: 'config.shortcuts', label: 'Shortcuts', action: () => frame.value?.openDialog('shortcuts') }] },
  {
    label: 'Help',
    items: [
      { id: 'help.ask', label: 'Ask ai', action: () => frame.value?.ask('@ai ') },
      { id: 'help.how-to', label: 'How do I…?', disabled: true },
      { id: 'help.docs', label: 'Documentation', disabled: true },
      { id: 'help.about', label: 'About claudia', action: () => frame.value?.openDialog('about') },
    ],
  },
])
</script>

<template>
  <DocumentFrame ref="frame" :session="session" :menus="menus" @leave="(opts) => emit('leave', opts)" @saved="canvas?.focus()">
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
  color: var(--ink); /* `--mist` stays light in dark mode */
}
.tabs button.on {
  /* `--app-soft` mixes with literal `white` (tokens.css), so it stays light regardless of theme — `--app-dark` as
   * its text is already theme-stable for the same reason as `StyleSpec.vue`'s `.marks button[aria-pressed]`; do
   * not swap to `--app-text`, which would put light-mode-only-safe light text on this still-light background. */
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
</style>
