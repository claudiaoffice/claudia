<script setup lang="ts">
// A presentation: the slide, the tool bar to put things on it, the slides along the bottom and the panel.
import { computed, ref } from 'vue'
import { insertFrame, type Frame } from '~/lib/geometry'
import type { SlideSession } from '~/lib/slide-session'
import { copySelection, cutSelection, pasteAsPlainText } from '~/lib/clipboard'
import { useI18n } from '~/lib/i18n'
import { objectStyleHost } from '~/lib/object-style-host'
import { useGrid } from '~/lib/grid'
import { useTheme } from '~/lib/theme'
import DocumentFrame from './DocumentFrame.vue'
import SlideCanvas from './SlideCanvas.vue'
import ImageImportDialog from './ImageImportDialog.vue'
import type { Menu } from './MenuBar.vue'

const props = defineProps<{ session: SlideSession }>()
const emit = defineEmits<{ leave: [opts?: { startFresh?: boolean }] }>()

const session = props.session
const state = session.state
const { dark, toggle: toggleDark } = useTheme()
// `t` stays this bare (never `i18n.t`): `scripts/extract_i18n.py`'s own regex only recognises an unqualified
// `t(...)` call (`obj.t(...)` is deliberately excluded, the same way `format(...)` is) -- see its docstring.
const { t, locale, choose } = useI18n()
const { shown: gridShown, toggle: toggleGrid } = useGrid()
const frame = ref<InstanceType<typeof DocumentFrame> | null>(null)
const canvas = ref<InstanceType<typeof SlideCanvas> | null>(null)
const showImageDialog = ref(false)
/** The modal layer: creates had only the image dialog before the styles arrived. */
const dialog = ref<null | 'styles' | 'colours'>(null)
const EXPORT_FORMATS = [{ value: 'pptx', label: 'PowerPoint presentation (.pptx)' }]

const readonly = computed(() => state.me.role === 'viewer')
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
  get bodies() {
    return session.bodies()
  },
  setObjectStyle: (id, style) => session.setObjectStyle(id, style),
  changeStyle: (style, edit) => session.changeStyle(style, edit),
  deviateObjectStyle: (parent, ids, edit) => session.deviateObjectStyle(parent, ids, edit),
  renameStyle: (style, name) => session.renameStyle(style, name),
  checkCss: (text) => session.checkCss(text),
  setRole: (role, colour) => session.setRole(role, colour),
})

/**
 * The Format menu: the styles by purpose first, because you mark a thing by what it is *for* (D62), then the two
 * ways in — this object's own look, and the document's colours.
 *
 * Styling needs something selected: with nothing selected there is nothing for a change to be about, so the
 * per-object items say so rather than failing quietly. Colours are the document's and never need a selection.
 */
function styleItems() {
  const styles = session.styleViews()
  if (styles.length === 0) return [{ label: t('No styles yet'), disabled: true }]
  const chosen = state.selected ? state.objects[state.selected]?.style : undefined
  return [
    ...styles.map((s) => ({
      label: s.name,
      checked: s.id === chosen,
      disabled: readonly.value || !state.selected,
      action: () => session.setObjectStyle(state.selected ?? '', s.id),
    })),
    { label: '', separator: true },
    {
      id: 'format.look',
      label: t('Edit this style…'),
      disabled: !state.selected,
      action: () => canvas.value?.openStyleMenu(),
    },
    { id: 'format.all-styles', label: t('All styles…'), action: () => (dialog.value = 'styles') },
    { label: '', separator: true },
    { id: 'format.colours', label: t('Colours…'), action: () => (dialog.value = 'colours') },
  ]
}

/** Put the colours the document started with back, as the server itself states them (no second copy to drift). */
async function resetPalette() {
  const started = state.palette?.builtin ?? []
  if (started.length && (await session.replacePalette(started))) dialog.value = null
}
const here = computed(() => state.slides.findIndex((s) => s.id === state.activeSlide))
const count = computed(() => session.objectsOn(state.activeSlide).length)

async function addText() {
  if (await session.addText(insertFrame('text', null, count.value))) canvas.value?.focus()
}
async function addShape(id: string) {
  const outline = state.library.find((s) => s.id === id) ?? state.shapes[id]
  if (await session.addShape(id, insertFrame('shape', outline?.aspect ?? null, count.value))) canvas.value?.focus()
}
function imageFrame(aspect: number): Frame {
  return insertFrame('image', aspect, count.value)
}
function imageInserted() {
  showImageDialog.value = false
  canvas.value?.focus()
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
    label: t('File'),
    items: [
      { id: 'file.new', label: t('New'), action: () => emit('leave', { startFresh: true }) },
      { id: 'file.open', label: t('Open…'), action: () => emit('leave') },
      { label: '', separator: true },
      { id: 'file.save', label: t('Save'), hint: 'Ctrl+S', action: () => frame.value?.checkpoint(null), disabled: readonly.value },
      { id: 'file.save-as', label: t('Save new checkpoint…'), action: () => frame.value?.openDialog('checkpoint'), disabled: readonly.value },
      { id: 'file.download', label: t('Download'), action: () => frame.value?.openDialog('export') },
      { label: '', separator: true },
      {
        id: 'file.manage',
        label: t('Manage'),
        items: [
          { id: 'file.manage.share', label: t('Share…'), action: () => frame.value?.openDialog('share'), disabled: state.me.role !== 'owner' },
          {
            id: 'file.manage.assign-owner',
            label: t('Assign new owner…'),
            action: () => frame.value?.openDialog('assign-owner'),
            disabled: state.me.role !== 'owner',
          },
          {
            id: 'file.manage.accept-owner',
            label: t('Accept ownership…'),
            action: () => frame.value?.openDialog('accept-owner'),
            disabled: state.me.role === 'viewer',
          },
          { id: 'file.manage.leave', label: t('Leave document…'), action: () => frame.value?.openDialog('leave') },
          { id: 'file.manage.export', label: t('Export…'), action: () => frame.value?.openDialog('export-format') },
          {
            id: 'file.manage.delete',
            label: t('Delete from server…'),
            action: () => frame.value?.openDialog('delete'),
            disabled: state.me.role !== 'owner',
          },
        ],
      },
      { label: '', separator: true },
      { id: 'file.close', label: t('Close document'), action: () => emit('leave') },
    ],
  },
  {
    label: t('Edit'),
    items: [
      {
        id: 'edit.undo',
        label: state.canUndo ? t('Undo {label}', { label: state.undoLabel }) : t('Undo'),
        hint: 'Ctrl+Z',
        action: () => session.undo(),
        disabled: !state.canUndo,
      },
      {
        id: 'edit.redo',
        label: state.canRedo ? t('Redo {label}', { label: state.redoLabel }) : t('Redo'),
        hint: 'Ctrl+Shift+Z',
        action: () => session.redo(),
        disabled: !state.canRedo,
      },
      { label: '', separator: true },
      { id: 'edit.copy', label: t('Copy'), hint: 'Ctrl+C', action: () => copySelection() },
      { id: 'edit.cut', label: t('Cut'), hint: 'Ctrl+X', action: () => cutSelection(), disabled: readonly.value },
      { id: 'edit.paste', label: t('Paste'), hint: 'Ctrl+V', action: () => pasteFromClipboard(), disabled: readonly.value },
      {
        id: 'edit.paste-as',
        label: t('Paste as'),
        disabled: readonly.value,
        // The child's own `disabled` is what a shell actually reports per-action (`collectStates` walks each item on
        // its own terms, not by inheriting a parent's); the parent's `disabled` above only keeps the web menu from
        // opening the flyout at all — both need to agree, or a shell could show the leaf as enabled regardless.
        items: [{ id: 'edit.paste-as-plain', label: t('Plain text'), action: () => pasteFromClipboard(), disabled: readonly.value }],
      },
      { label: '', separator: true },
      { id: 'edit.new-slide', label: t('New slide'), action: () => session.addSlide(), disabled: readonly.value },
      { label: '', separator: true },
      { id: 'edit.edit-text', label: t('Edit text'), hint: 'Enter', action: () => canvas.value?.beginEdit(), disabled: readonly.value || !state.selected },
      { id: 'edit.text-box', label: t('Text box'), action: () => addText(), disabled: readonly.value },
      { id: 'edit.image', label: t('Image…'), action: () => (showImageDialog.value = true), disabled: readonly.value },
      { label: '', separator: true },
      ...state.library.map((s) => ({ label: s.name, action: () => addShape(s.id), disabled: readonly.value })),
      { label: '', separator: true },
      { id: 'edit.delete', label: t('Delete'), hint: 'Del', action: () => remove(), disabled: readonly.value || !state.selected },
    ],
  },
  {
    label: t('Format'),
    items: styleItems(),
  },
  {
    label: t('View'),
    items: [
      { id: 'view.authors', label: t('Show who wrote what'), checked: false, disabled: true }, // creates tracks no per-object authorship yet
      {
        id: 'view.grid',
        label: 'Show grid',
        checked: gridShown.value,
        action: (t) => {
          if (t === undefined || (t === 'on') !== gridShown.value) toggleGrid()
        },
      },
      {
        id: 'view.panel',
        label: t('History and chat'),
        checked: frame.value?.isPanelOpen() ?? true,
        action: (x) => {
          const open = frame.value?.isPanelOpen() ?? true
          if (x === undefined || (x === 'on') !== open) frame.value?.togglePanel()
        },
      },
      {
        id: 'view.dark',
        label: t('Dark mode'),
        checked: dark(),
        action: (x) => {
          if (x === undefined || (x === 'on') !== dark()) toggleDark()
        },
      },
    ],
  },
  { label: t('Tools'), items: [{ id: 'tools.ask', label: t('Ask the assistant…'), action: () => frame.value?.ask('@ai ') }] },
  {
    label: t('Config'),
    items: [
      { id: 'config.shortcuts', label: t('Shortcuts'), action: () => frame.value?.openDialog('shortcuts') },
      {
        label: t('App Language'),
        items: [
          { id: 'config.language.en', label: 'English', checked: locale.value === 'en', action: () => choose('en') },
          { id: 'config.language.de', label: 'Deutsch', checked: locale.value === 'de', action: () => choose('de') },
        ],
      },
    ],
  },
  {
    label: t('Help'),
    items: [
      { id: 'help.ask', label: t('Ask ai'), action: () => frame.value?.ask('@ai ') },
      { id: 'help.how-to', label: t('How do I…?'), action: () => frame.value?.openHelp('how-to') },
      { id: 'help.docs', label: t('Documentation'), action: () => frame.value?.openHelp('docs') },
      { id: 'help.about', label: t('About claudia'), action: () => frame.value?.openDialog('about') },
    ],
  },
])
</script>

<template>
  <DocumentFrame ref="frame" :session="session" :menus="menus" :export-formats="EXPORT_FORMATS" @leave="(opts) => emit('leave', opts)" @saved="canvas?.focus()">
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
        @image="showImageDialog = true"
        @remove="remove"
        @undo="session.undo()"
        @redo="session.redo()"
      />
    </template>
    <SlideCanvas v-if="state.activeSlide" ref="canvas" :session="session" :show-grid="gridShown" @styles="dialog = 'styles'" />
    <div v-else class="noslide">This presentation has no slide.</div>
    <template #overlay>
      <ImageImportDialog v-if="showImageDialog" :session="session" :frame-for="imageFrame" @close="showImageDialog = false" @inserted="imageInserted" />
      <StylesDialog v-if="dialog === 'styles'" :host="styleHost" @close="dialog = null" />
      <PaletteDialog v-if="dialog === 'colours'" :host="styleHost" :builtin="state.palette?.builtin ?? []" @close="dialog = null" @reset="resetPalette" />
    </template>
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
