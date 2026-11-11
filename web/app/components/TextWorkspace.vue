<script setup lang="ts">
// A text: the style bar, the page, the suggestions above the panel, and the counts along the bottom, inside the
// document window every app shares (DocumentFrame).
import { computed, ref, watch } from 'vue'
import { countWords } from '~/lib/blocks'
import { toMarkdown } from '~/lib/markdown'
import { SAMPLE_TEXT } from '~/lib/sample'
import { textStyleHost } from '~/lib/text-style-host'
import type { TextSession } from '~/lib/text-session'
import type { StyleView } from '~/lib/style-css'
import {
  askItem,
  clipboardItems,
  configMenu,
  darkItem,
  fileMenu,
  helpMenu,
  panelItem,
  undoRedoItems,
  type DocumentMenuContext,
} from '~/lib/document-menus'
import { chordLabel, type ShortcutDef } from '~/lib/shortcuts'
import { useI18n } from '~/lib/i18n'
import { useTheme } from '~/lib/theme'
import DocumentFrame from './DocumentFrame.vue'
import type { Menu } from './MenuBar.vue'

const props = defineProps<{ session: TextSession }>()
const emit = defineEmits<{ leave: [opts?: { startFresh?: boolean }] }>()

const session = props.session
const state = session.state
const { dark, toggle: toggleDark } = useTheme()
// `t` stays this bare (never `i18n.t`): `scripts/extract_i18n.py`'s own regex only recognises an unqualified
// `t(...)` call (`obj.t(...)` is deliberately excluded, the same way `format(...)` is) -- see its docstring.
const { t, locale, choose } = useI18n()

const frame = ref<InstanceType<typeof DocumentFrame> | null>(null)
/** composes' own dialogs; the window's (save, share, export, …) are DocumentFrame's. */
const dialog = ref<null | 'styles' | 'colours'>(null)
const styleMenu = ref<{ x: number; y: number } | null>(null)
const styleHost = textStyleHost(session)
const active = ref<string | null>(null)
const editor = ref<{ focus: () => void; scrollToSuggestion: (id: string) => void; caretPoint: () => { x: number; y: number } } | null>(null)

// How I look at the text is mine alone (and is remembered in this browser).
function remembered<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = localStorage.getItem(key) as T | null
    return value && allowed.includes(value) ? value : fallback
  } catch {
    return fallback
  }
}
function remember(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* private window: nothing to remember */
  }
}
const view = ref<'flow' | 'page'>(remembered('claudia.composes.view', ['flow', 'page'], 'flow'))
const authors = ref(remembered('claudia.composes.authors', ['on', 'off'], 'off') === 'on')
watch(view, (v) => remember('claudia.composes.view', v))
watch(authors, (on) => remember('claudia.composes.authors', on ? 'on' : 'off'))

const readonly = computed(() => session.readOnly)
const words = computed(() => countWords(state.blocks))
const openSuggestions = computed(() => state.suggestions.filter((s) => s.state === 'open').length)

// ------------------------------------------------------------------------------ doing things
function pick(id: string) {
  active.value = id
  editor.value?.scrollToSuggestion(id)
}

/** File ▸ Export… (D212): Markdown is built here from `state.blocks`, Word by the server. The window sends what is
 * still being typed before it opens the dialog (`DocumentFrame.openDialog`), so both see the text as it stands. */
const exportFormats = [
  { value: 'md', label: 'Markdown (.md)', mimeType: 'text/markdown', local: () => toMarkdown(state.blocks) },
  { value: 'docx', label: 'Word document (.docx)' },
]

function openStyleMenu(at = editor.value?.caretPoint() ?? { x: 80, y: 120 }) {
  styleMenu.value = at
}

/** Put the colours the document started with back: a real `replace_palette`, in the history like any edit.
 *
 * The set comes from the server's own `palette` answer, so there is no second copy of the nine roles to drift. */
async function resetPalette() {
  const started = state.palette?.builtin ?? []
  if (started.length && (await session.replacePalette(started))) dialog.value = null
}

function closeStyleMenu() {
  styleMenu.value = null
  editor.value?.focus()
}

function insertSample() {
  session.paste(SAMPLE_TEXT)
  editor.value?.focus()
}

// composes has one way to bring text in, however it arrives (typed, "Paste", or "Paste as plain text") — there is no
// separate rich-paste path yet, so the two Edit items below are, honestly, the same operation.
async function pasteFromClipboard() {
  let text: string
  try {
    text = await navigator.clipboard.readText()
  } catch {
    return // no permission, no secure context, or nothing textual on the clipboard — same as a native paste finding nothing
  }
  if (text) {
    session.paste(text)
    editor.value?.focus()
  }
}

// ------------------------------------------------------------------------------ menus and shortcuts
// D122: composes' one shortcut of its own, on top of the window's Undo, Redo and Save.
const LOOK: ShortcutDef = { id: 'format.look', label: 'Edit this style…', chord: { key: 'F10', shift: true }, run: () => openStyleMenu() }
const extraShortcuts = [LOOK]

/** What the shared menu items need from this window (`lib/document-menus.ts`). */
const shared = computed<DocumentMenuContext>(() => ({
  t,
  role: state.me.role,
  open: (name) => frame.value?.openDialog(name),
  leave: (opts) => emit('leave', opts),
  save: () => frame.value?.checkpoint(null),
}))

function ask(text: string) {
  frame.value?.ask(text)
}

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
      ],
    },
    {
      label: t('Format'),
      items:
        state.styles.length === 0
          ? [{ label: t('No styles yet'), disabled: true }]
          : [
              ...['title', 'heading-1', 'heading-2'].map((id) => styleItem(id)),
              { label: '', separator: true },
              ...['body'].map((id) => styleItem(id)),
              { label: '', separator: true },
              ...['quote', 'remark', 'definition'].map((id) => styleItem(id)),
              ...customStyleItems(),
              { label: '', separator: true },
              { id: 'format.look', label: t('Edit this style…'), hint: chordLabel(LOOK.chord), action: () => openStyleMenu() },
              { id: 'format.all-styles', label: t('All styles…'), action: () => (dialog.value = 'styles') },
              { label: '', separator: true },
              // The palette reaches composes' paragraph styles from day one (D200): a heading's colour is a role.
              { id: 'format.colours', label: t('Colours…'), action: () => (dialog.value = 'colours') },
            ],
    },
    {
      label: t('View'),
      items: [
        { id: 'view.authors', label: t('Show who wrote what'), checked: authors.value, action: (x) => (authors.value = x ? x === 'on' : !authors.value) },
        panelItem(c, { open: () => frame.value?.isPanelOpen() ?? true, toggle: () => frame.value?.togglePanel() }),
        darkItem(c, { on: dark, toggle: toggleDark }),
        { label: '', separator: true },
        { label: t('Flow'), checked: view.value === 'flow', action: () => (view.value = 'flow') },
        // One boolean action (GTK has no notion of two radio items), set/cleared explicitly by a shell, toggled by a web click.
        { id: 'view.page', label: t('Page'), checked: view.value === 'page', action: (x) => (view.value = x === 'off' ? 'flow' : 'page') },
      ],
    },
    {
      label: t('Tools'),
      items: [
        askItem(c, ask),
        { id: 'tools.review-text', label: t('Review this text'), action: () => ask('@ai review this text') },
        { id: 'tools.review-paragraph', label: t('Review this paragraph'), action: () => ask('@ai check this paragraph') },
        { label: '', separator: true },
        { id: 'tools.insert-sample', label: t('Insert sample text'), action: insertSample, disabled: readonly.value },
      ],
    },
    configMenu(c, { current: locale.value, choose }),
    helpMenu(c, { ask, openHelp: (mode) => frame.value?.openHelp(mode) }),
  ]
})

/** One Format-menu entry for a built-in style, by id — kept as a function rather than inlining `state.styles.find`
 * three times over, since the three groups below (D127: structure · running text · called-out blocks) each pick a
 * fixed subset of the seven built-in ids, not a contiguous slice. */
function styleItem(id: string) {
  const s = state.styles.find((s) => s.id === id)
  return {
    label: s?.name ?? id,
    checked: session.currentStyle() === id,
    action: () => {
      void session.setStyle(id)
      editor.value?.focus()
    },
    disabled: readonly.value || !s,
  }
}
const BUILTIN_STYLE_IDS = new Set(['body', 'title', 'heading-1', 'heading-2', 'quote', 'remark', 'definition'])
/**
 * A text's style book holds the floating objects' styles too, since one object layer serves all three apps
 * (E10.16). The *Format* menu marks a paragraph, so it lists only the styles that fit a paragraph: a paragraph is
 * one slot that takes paragraph styles (D304, D316), which leaves out `plain-shape`, `plain-box` and `plain-image`
 * by their kind, and with them every style somebody deviated from one of them.
 *
 * `shape-label` is a paragraph style by kind but was made for the words in a shape, not for a paragraph of the text
 * (D310), so it is left out by name. Which slots a style is *meant* for, beyond which it fits, is a question for the
 * new style menu (the styling-suite plan, step 2.2).
 */
const OBJECT_WORDS_STYLE_IDS = new Set(['shape-label'])
const forParagraphs = (s: StyleView) => s.kind === 'paragraph' && !OBJECT_WORDS_STYLE_IDS.has(s.id)
/** A style made by deviating from a built-in (`next_style` in `model.py`) is not one of the three fixed groups above
 * — D127 only grouped the seven built-ins, so anything else gets its own trailing group rather than being folded
 * silently into one of them. */
function customStyleItems() {
  const custom = state.styles.filter((s) => !BUILTIN_STYLE_IDS.has(s.id) && forParagraphs(s))
  if (!custom.length) return []
  return [{ label: '', separator: true }, ...custom.map((s) => styleItem(s.id))]
}

// Config ▸ Shortcuts (D122/D126): the things that are not a `keydown` shortcut at all — typing itself, and native
// Ctrl+C/X/V, which the browser already handles for whatever has focus.
const SHORTCUT_NOTES: [string, string][] = [
  ['Type', 'write; a word is sent when it ends, and the others see where you are'],
  ['Enter', 'end the paragraph (after a heading the next one is body text)'],
  ['Backspace / Delete', 'delete; at the edge of a paragraph it joins the one next to it'],
  ['Ctrl + Backspace / Delete', 'delete a word'],
  ['Ctrl + C / X / V', 'copy, cut and paste, also from and to other programs'],
  ['@ai review this text', 'the assistant suggests changes; you accept or reject each'],
]
</script>

<template>
  <DocumentFrame
    ref="frame"
    app="composes"
    data-testid="text-workspace"
    :session="session"
    :menus="menus"
    :export-formats="exportFormats"
    :extra-shortcuts="extraShortcuts"
    :shortcut-notes="SHORTCUT_NOTES"
    @leave="(opts) => emit('leave', opts)"
  >
    <template #toolbar>
      <StyleBar :session="session" :view="view" :authors="authors" @view="view = $event" @authors="authors = $event" @styled="editor?.focus()" @look="openStyleMenu" />
    </template>
    <TextEditor ref="editor" :session="session" :view="view" :authors="authors" :active="active" @suggestion="pick" @style-menu="openStyleMenu" />
    <template #side-top><SuggestionList :session="session" :active="active" @pick="pick" /></template>
    <template #footer>
      <footer class="foot">
        <div class="stats mono" aria-live="polite">
          <span><b data-testid="words">{{ words }}</b> {{ words === 1 ? 'word' : 'words' }}</span>
          <span><b>{{ state.blocks.length }}</b> {{ state.blocks.length === 1 ? 'paragraph' : 'paragraphs' }}</span>
          <span v-if="openSuggestions"><b>{{ openSuggestions }}</b> {{ openSuggestions === 1 ? 'suggestion' : 'suggestions' }}</span>
        </div>
        <span class="rev mono" :title="`line ${state.line}`">{{ state.revision ?? 'empty' }}</span>
      </footer>
    </template>
    <template #overlay>
      <StyleMenu v-if="styleMenu" :host="styleHost" :x="styleMenu.x" :y="styleMenu.y" @close="closeStyleMenu" @styles="(styleMenu = null), (dialog = 'styles')" />
      <StylesDialog v-if="dialog === 'styles'" :host="styleHost" @close="dialog = null" />
      <PaletteDialog v-if="dialog === 'colours'" :host="styleHost" :builtin="state.palette?.builtin ?? []" @close="dialog = null" @reset="resetPalette" />
    </template>
  </DocumentFrame>
</template>

<style scoped>
.foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  height: 32px;
  padding: 0 14px;
  background: var(--surface);
  border-top: 1px solid var(--line);
  font-size: 12px;
  color: var(--muted);
}
.stats {
  display: flex;
  gap: 16px;
}
.stats b {
  color: var(--text);
  font-weight: 500;
}
</style>
