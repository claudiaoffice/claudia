<script setup lang="ts">
// A presentation: the slide, the tool bar to put things on it, the slides along the bottom and the panel.
import { computed, ref } from 'vue'
import { insertFrame, type Frame } from '~/lib/geometry'
import type { SlideSession } from '~/lib/slide-session'
import { pasteAsPlainText } from '~/lib/clipboard'
import {
  askItem,
  authorsItemUnavailable,
  clipboardItems,
  configMenu,
  darkItem,
  fileMenu,
  helpMenu,
  panelItem,
  undoRedoItems,
  type DocumentMenuContext,
} from '~/lib/document-menus'
import { useI18n } from '~/lib/i18n'
import { objectStyleHost, type ObjectStyling } from '~/lib/object-style-host'
import { galleryFor } from '~/lib/style-host'
import { describeShortcut } from '~/lib/descriptions'
import { chordLabel } from '~/lib/shortcuts'
import { formatItems, noLists } from '~/lib/format-menu'
import { useGrid } from '~/lib/grid'
import { useTheme } from '~/lib/theme'
import DocumentFrame from './DocumentFrame.vue'
import SlideCanvas from './SlideCanvas.vue'
import ImageImportDialog from './ImageImportDialog.vue'
import PrintPreview from './PrintPreview.vue'
import { slideSource } from '~/lib/print/source'
import { useCreatorLanguage, usePrint } from '~/lib/print/use-print'
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
const EXPORT_FORMATS = [
  { value: 'pptx', get label() { return t('PowerPoint presentation (.pptx)') } },
  { value: 'odp', get label() { return t('OpenDocument presentation (.odp)') } },
]

const readonly = computed(() => state.me.role === 'viewer')

// A new presentation starts in the language of its maker's interface (D915, D917); File ▸ Print… shows the pages in
// place of the slide (D906, D918). Both as in every app that prints (`lib/print/use-print.ts`).
useCreatorLanguage(session, () => locale.value)
const { printing, preview, open: openPrint, close: closePrint, shortcut: PRINT } = usePrint(() => canvas.value?.focus())
const printSource = slideSource(session)
const describeSelected = describeShortcut(
  () => canvas.value?.openDescribe(),
  () => state.selected !== null && !readonly.value,
)
const extraShortcuts = [PRINT, describeSelected]
const styling: ObjectStyling = {
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
}
/** The Format menu's and the bar's host: the slot an object is mostly styled by (a text box's words, a shape's
 * outline, a picture's box). */
const styleHost = objectStyleHost(styling)
/** The bar's second picker, for a shape's words (D310: the outline and the label are two slots). */
const labelHost = objectStyleHost(styling, 'label')
const selectedKind = computed(() => (state.selected ? state.objects[state.selected]?.kind : undefined))

/**
 * The Format menu (D300): Apply style ▸ with the styles that fit the selected object's slot — the one the style
 * menu works on, a shape's outline or a text box's words (D304, D316) — then this object's own look, all the
 * styles, and the document's colours. Styling needs something selected; colours never do.
 */
function styleItems() {
  if (session.styleViews().length === 0) return [{ label: t('No styles yet'), disabled: true }]
  const body = state.selected ? state.objects[state.selected] : undefined
  const offered = galleryFor(styleHost.styles, styleHost.slot, state.styleModel)
  return formatItems(t, {
    groups: body ? [offered.own, offered.bundles] : [],
    heading: body ? undefined : t('Select an object to style it'),
    current: styleHost.current?.id,
    canApply: !readonly.value && !!body,
    apply: (id) => void styleHost.apply(id),
    openApply: () => canvas.value?.openStyleMenu(undefined, 'apply'),
    look: { disabled: !body, open: () => canvas.value?.openStyleMenu() },
    allStyles: () => (dialog.value = 'styles'),
    colours: () => (dialog.value = 'colours'),
    list: noLists(t('Text boxes hold no lists yet')),
  })
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

/** What the shared menu items need from this window (`lib/document-menus.ts`). */
const shared = computed<DocumentMenuContext>(() => ({
  t,
  role: state.me.role,
  open: (dialog) => frame.value?.openDialog(dialog),
  leave: (opts) => emit('leave', opts),
  save: () => frame.value?.checkpoint(null),
  print: openPrint,
}))

const menus = computed<Menu[]>(() => {
  const c = shared.value
  return [
    fileMenu(c),
    {
      label: t('Edit'),
      items: [
        ...undoRedoItems(c, {
          canUndo: state.canUndo,
          undoLabel: state.undoLabel,
          canRedo: state.canRedo,
          redoLabel: state.redoLabel,
          undo: () => session.undo(),
          redo: () => session.redo(),
        }),
        { label: '', separator: true },
        ...clipboardItems(c, () => pasteFromClipboard()),
        { label: '', separator: true },
        { id: 'edit.new-slide', label: t('New Slide'), action: () => session.addSlide(), disabled: readonly.value },
        { label: '', separator: true },
        { id: 'edit.edit-text', label: t('Edit Text'), hint: 'Enter', action: () => canvas.value?.beginEdit(), disabled: readonly.value || !state.selected },
        { id: 'edit.text-box', label: t('Text Box'), action: () => addText(), disabled: readonly.value },
        { id: 'edit.image', label: t('Image…'), action: () => (showImageDialog.value = true), disabled: readonly.value },
        { label: '', separator: true },
        ...state.library.map((s) => ({ label: s.name, action: () => addShape(s.id), disabled: readonly.value })),
        { label: '', separator: true },
        { id: 'edit.delete', label: t('Delete'), hint: 'Del', action: () => remove(), disabled: readonly.value || !state.selected },
      ],
    },
    {
      label: t('Format'),
      items: [
        ...styleItems(),
        { label: '', separator: true },
        { id: 'format.describe', label: t('Describe Object…'), hint: chordLabel(describeSelected.chord), action: () => canvas.value?.openDescribe(), disabled: readonly.value || !state.selected },
      ],
    },
    {
      label: t('View'),
      items: [
        authorsItemUnavailable(c), // creates tracks no per-object authorship yet
        {
          id: 'view.grid',
          label: t('Show grid'),
          checked: gridShown.value,
          action: (x) => {
            if (x === undefined || (x === 'on') !== gridShown.value) toggleGrid()
          },
        },
        panelItem(c, { open: () => frame.value?.isPanelOpen() ?? true, toggle: () => frame.value?.togglePanel() }),
        darkItem(c, { on: dark, toggle: toggleDark }),
      ],
    },
    { label: t('Tools'), items: [askItem(c, (text) => frame.value?.ask(text))] },
    configMenu(c, { current: locale.value, choose }),
    helpMenu(c, { ask: (text) => frame.value?.ask(text), openHelp: (mode) => frame.value?.openHelp(mode) }),
  ]
})

/** Config ▸ Shortcuts: the slide's own mouse and keyboard conventions, which are not a single key chord. */
const SHORTCUT_NOTES = computed<[string, string][]>(() => [
  [t('Click'), t('select an object (colleagues cannot change it while you hold it)')],
  [t('Drag'), t('move it; the handles resize it')],
  [t('Double-click, Enter'), t('write in it; Enter keeps the text, Shift+Enter starts a line, Esc drops it')],
  [t('Arrows'), t('move it by 10 units; with Shift by 1')],
  [t('Ctrl + C / X / V'), t('copy, cut and paste, also from and to other programs')],
])
</script>

<template>
  <DocumentFrame
    ref="frame"
    app="creates"
    :session="session"
    :menus="menus"
    :export-formats="EXPORT_FORMATS"
    :extra-shortcuts="extraShortcuts"
    :shortcut-notes="SHORTCUT_NOTES"
    @leave="(opts) => emit('leave', opts)"
    @saved="canvas?.focus()"
  >
    <template #toolbar>
      <InsertBar
        v-if="!printing"
        data-region="toolbar"
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
      >
        <!-- Applying a style where composes and computes have it (owner's report, 2026-11-12): the popover only shows a
             style's look (UX-14), so without this a named style could be applied only from Format ▸ Apply style. -->
        <StylePicker :host="styleHost" :hint="'Shift+F10'" @look="canvas?.openStyleMenu()" @styled="canvas?.focus()" />
        <StylePicker v-if="selectedKind === 'shape'" :host="labelHost" :caption="t('Label')" testid="label-picker" @look="canvas?.openStyleMenu()" @styled="canvas?.focus()" />
      </InsertBar>
    </template>
    <PrintPreview v-if="printing" ref="preview" :source="printSource" @close="closePrint" />
    <SlideCanvas v-else-if="state.activeSlide" ref="canvas" data-region="document" :session="session" :show-grid="gridShown" @styles="dialog = 'styles'" />
    <div v-else class="noslide">{{ t('This presentation has no slide.') }}</div>
    <template #overlay>
      <ImageImportDialog v-if="showImageDialog" :session="session" :frame-for="imageFrame" @close="showImageDialog = false" @inserted="imageInserted" />
      <StylesDialog v-if="dialog === 'styles'" :host="styleHost" @close="dialog = null" />
      <PaletteDialog v-if="dialog === 'colours'" :host="styleHost" :builtin="state.palette?.builtin ?? []" @close="dialog = null" @reset="resetPalette" />
    </template>
    <template #footer>
      <footer v-if="!printing" class="foot">
        <div class="tabs" role="tablist" :aria-label="t('slides')">
          <button
            v-for="(s, i) in state.slides"
            :key="s.id"
            type="button"
            role="tab"
            :aria-selected="s.id === state.activeSlide"
            :class="{ on: s.id === state.activeSlide }"
            @click="session.showSlide(s.id)"
          >
            {{ t('Slide {n}', { n: i + 1 }) }}
          </button>
          <button v-if="!readonly" type="button" class="add" :title="t('New Slide')" :aria-label="t('new slide')" @click="session.addSlide()">+</button>
        </div>
        <div class="stats mono">
          <span v-if="here >= 0">{{ here + 1 }} / {{ state.slides.length }}</span>
          <span class="rev" :title="t('line {line}', { line: state.line })">{{ state.revision ?? t('empty') }}</span>
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
</style>
