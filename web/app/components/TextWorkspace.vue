<script setup lang="ts">
// A text: the style bar, the page, the suggestions above the panel, and the counts along the bottom, inside the
// document window every app shares (DocumentFrame).
import { computed, ref, watch } from 'vue'
import { countWords } from '~/lib/blocks'
import { toMarkdown } from '~/lib/markdown'
import { textStyleHost } from '~/lib/text-style-host'
import type { TextSession } from '~/lib/text-session'
import type { StyleView } from '~/lib/style-css'
import { formatItems } from '~/lib/format-menu'
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
import PrintPreview from './PrintPreview.vue'
import { textSource } from '~/lib/print/source'
import { useCreatorLanguage, usePrint } from '~/lib/print/use-print'
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
const dialog = ref<null | 'styles' | 'colours' | 'list-start'>(null)
const styleMenu = ref<{ x: number; y: number; mode?: 'edit' | 'apply' } | null>(null)
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

// A new text starts in the language of its maker's interface (D915); File ▸ Print… shows the pages in place of the
// text (D906, D918). Both as in every app that prints (`lib/print/use-print.ts`).
useCreatorLanguage(session, () => locale.value)
const { printing, preview, open: openPrint, close: closePrint, shortcut: PRINT } = usePrint(() => editor.value?.focus())
const printSource = textSource(session)

const readonly = computed(() => session.readOnly)
const words = computed(() => countWords(state.blocks))
const openSuggestions = computed(() => state.suggestions.filter((s) => s.state === 'open').length)

// ------------------------------------------------------------------------------ doing things
/** The suggestion opened where it is marked (`SuggestionPopover.vue`), and where its card shows. */
const opened = ref<{ id: string; x: number; y: number } | null>(null)

function pick(id: string) {
  active.value = id
  editor.value?.scrollToSuggestion(id)
  // Under its mark once the scroll has settled; in the middle of the text if the mark is not on screen.
  setTimeout(() => {
    const mark = document.querySelector<HTMLElement>(`[data-testid=text] [data-sug="${CSS.escape(id)}"]`)
    const r = mark?.getBoundingClientRect()
    opened.value = r ? { id, x: r.left, y: r.bottom + 6 } : { id, x: window.innerWidth / 3, y: window.innerHeight / 3 }
  }, 250)
}

/** The bottom bar's count, and the card's "Next": the first open suggestion after `after`, in the order of the text. */
function pickNext(after?: string) {
  const open = state.suggestions.filter((s) => s.state === 'open')
  const order = state.blocks.map((b) => b.id)
  open.sort((a, b) => order.indexOf(a.block) - order.indexOf(b.block) || a.start - b.start)
  const at = after ? open.findIndex((s) => s.id === after) : -1
  const next = open[(at + 1) % Math.max(open.length, 1)]
  if (next) pick(next.id)
  else closeSuggestion()
}
function closeSuggestion() {
  opened.value = null
  active.value = null
}

/** File ▸ Export… (D212, D401): Markdown is built here from `state.blocks`, Word and OpenDocument text by the server. The window sends what is
 * still being typed before it opens the dialog (`DocumentFrame.openDialog`), so both see the text as it stands. */
const exportFormats = [
  { value: 'md', label: 'Markdown (.md)', mimeType: 'text/markdown', local: () => toMarkdown(state.blocks) },
  { value: 'docx', label: 'Word document (.docx)' },
  { value: 'odt', label: 'OpenDocument text (.odt)' },
]

function openStyleMenu(at = editor.value?.caretPoint() ?? { x: 80, y: 120 }, mode: 'edit' | 'apply' = 'edit') {
  styleMenu.value = { ...at, mode }
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
// D912: a soft hyphen says where a word may be broken, a non-breaking hyphen where it may not (as in Word and
// LibreOffice). Both are invisible in the text unless the pages break there.
const typing = () => !printing.value && !session.readOnly
const SOFT_HYPHEN: ShortcutDef = { id: 'edit.soft-hyphen', label: 'Soft hyphen', chord: { key: '-', ctrl: true }, run: () => session.type('\u00ad'), enabled: typing }
const HARD_HYPHEN: ShortcutDef = { id: 'edit.nonbreaking-hyphen', label: 'Non-breaking hyphen', chord: { key: '_', ctrl: true, shift: true }, run: () => session.type('\u2011'), enabled: typing }
// E9.21: bullets and numbers, on the keys of the digits (Google Docs' Ctrl+Shift+8 and 7), whatever they type.
const BULLETS: ShortcutDef = { id: 'format.bulleted-list', label: 'Bulleted list', chord: { key: '8', code: 'Digit8', ctrl: true, shift: true }, run: () => makeList('bullets'), enabled: () => !readonly.value }
const NUMBERS: ShortcutDef = { id: 'format.numbered-list', label: 'Numbered list', chord: { key: '7', code: 'Digit7', ctrl: true, shift: true }, run: () => makeList('numbers'), enabled: () => !readonly.value }
const extraShortcuts = [LOOK, PRINT, SOFT_HYPHEN, HARD_HYPHEN, BULLETS, NUMBERS]

function makeList(scheme: 'bullets' | 'numbers') {
  void session.makeList(scheme)
  editor.value?.focus()
}

/** The kind of list the caret is in, if it is one of the two the menu names. */
const currentKind = () => (['bullets', 'numbers'] as const).find((kind) => kind === session.currentScheme()) ?? null

function startListAt(value: string) {
  const start = Number.parseInt(value, 10)
  if (Number.isInteger(start) && start >= 1 && start <= 999999) {
    void session.startAt(start)
    dialog.value = null
    editor.value?.focus()
  }
}
const listStart = () => String(state.lists.find((l) => l.id === session.currentItem()?.list)?.start ?? 1)

/** What the shared menu items need from this window (`lib/document-menus.ts`). */
const shared = computed<DocumentMenuContext>(() => ({
  t,
  role: state.me.role,
  open: (name) => frame.value?.openDialog(name),
  leave: (opts) => emit('leave', opts),
  save: () => frame.value?.checkpoint(null),
  print: openPrint,
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
          : formatItems(t, {
              // D127's groups — structure · running text · called-out blocks — and then any style of the text's own.
              groups: [builtins(['title', 'heading-1', 'heading-2']), builtins(['body']), builtins(['quote', 'remark', 'definition']), customStyles()],
              current: session.currentStyle(),
              canApply: !readonly.value,
              apply: (id) => {
                void session.setStyle(id)
                editor.value?.focus()
              },
              openApply: () => openStyleMenu(undefined, 'apply'),
              look: { disabled: false, hint: chordLabel(LOOK.chord), open: () => openStyleMenu() },
              allStyles: () => (dialog.value = 'styles'),
              // The palette reaches composes' paragraph styles from day one (D200): a heading's colour is a role.
              colours: () => (dialog.value = 'colours'),
              list: {
                readonly: readonly.value,
                current: currentKind(),
                canNest: !!session.currentItem(),
                canContinue: session.canContinue(),
                hints: { bulleted: chordLabel(BULLETS.chord), numbered: chordLabel(NUMBERS.chord), indent: 'Tab', outdent: 'Shift+Tab' },
                bulleted: () => makeList('bullets'),
                numbered: () => makeList('numbers'),
                continueList: () => void session.continueList(),
                startAt: () => (dialog.value = 'list-start'),
                indent: () => void session.indent(1),
                outdent: () => void session.indent(-1),
              },
            }),
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
        // Only the generic "Ask ai" (D126). The canned demo requests ("Review this text", "Review this paragraph") and
        // "Insert sample text" were taken out at the owner's request (2026-11-12): demo props, not features.
        askItem(c, ask),
      ],
    },
    configMenu(c, { current: locale.value, choose }),
    helpMenu(c, { ask, openHelp: (mode) => frame.value?.openHelp(mode) }),
  ]
})

/** The built-in styles of one of D127's groups (structure · running text · called-out blocks), by id, in order. */
function builtins(ids: string[]): StyleView[] {
  return ids.map((id) => state.styles.find((s) => s.id === id)).filter((s): s is StyleView => !!s)
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
function customStyles(): StyleView[] {
  return state.styles.filter((s) => !BUILTIN_STYLE_IDS.has(s.id) && forParagraphs(s))
}

// Config ▸ Shortcuts (D122/D126): the things that are not a `keydown` shortcut at all — typing itself, and native
// Ctrl+C/X/V, which the browser already handles for whatever has focus.
const SHORTCUT_NOTES: [string, string][] = [
  ['Type', 'write; a word is sent when it ends, and the others see where you are'],
  ['Enter', 'end the paragraph (after a heading the next one is body text); in a list, the next item; on an empty item, out of the list'],
  ['Tab / Shift + Tab', 'in a list, one level in or out'],
  ['Backspace / Delete', 'delete; at the edge of a paragraph it joins the one next to it'],
  ['Ctrl + Backspace / Delete', 'delete a word'],
  ['Ctrl + C / X / V', 'copy, cut and paste, also from and to other programs'],
  ['Ctrl + -', 'a soft hyphen: where a word may be broken at the end of a line in the pages'],
  ['Ctrl + Shift + -', 'a non-breaking hyphen: a hyphen the line is never broken after'],
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
      <StyleBar v-if="!printing" :session="session" :view="view" :authors="authors" @view="view = $event" @authors="authors = $event" @styled="editor?.focus()" @look="openStyleMenu" />
    </template>
    <PrintPreview v-if="printing" ref="preview" :source="printSource" @close="closePrint" />
    <TextEditor v-else ref="editor" :session="session" :view="view" :authors="authors" :active="active" @suggestion="pick" @style-menu="openStyleMenu" />
    <template #footer>
      <footer v-if="!printing" class="foot">
        <div class="stats mono" aria-live="polite">
          <span><b data-testid="words">{{ words }}</b> {{ words === 1 ? 'word' : 'words' }}</span>
          <span><b>{{ state.blocks.length }}</b> {{ state.blocks.length === 1 ? 'paragraph' : 'paragraphs' }}</span>
          <button v-if="openSuggestions" type="button" class="sugs" data-testid="open-suggestions" title="Open the first suggestion" @click="pickNext()"><b>{{ openSuggestions }}</b> {{ openSuggestions === 1 ? 'suggestion' : 'suggestions' }}</button>
        </div>
        <span class="rev mono" :title="`line ${state.line}`">{{ state.revision ?? 'empty' }}</span>
      </footer>
    </template>
    <template #overlay>
      <SuggestionPopover v-if="opened" :id="opened.id" :key="opened.id" :session="session" :x="opened.x" :y="opened.y" @close="closeSuggestion" @next="pickNext(opened.id)" />
      <StyleMenu v-if="styleMenu" :host="styleHost" :x="styleMenu.x" :y="styleMenu.y" :mode="styleMenu.mode" @close="closeStyleMenu" @styles="(styleMenu = null), (dialog = 'styles')" />
      <StylesDialog v-if="dialog === 'styles'" :host="styleHost" @close="dialog = null" />
      <PromptDialog v-if="dialog === 'list-start'" title="Start numbering at" label="First number" ok="Start" required :initial="listStart()" @ok="startListAt" @close="dialog = null" />
      <PaletteDialog v-if="dialog === 'colours'" :host="styleHost" :builtin="state.palette?.builtin ?? []" @close="dialog = null" @reset="resetPalette" />
    </template>
  </DocumentFrame>
</template>

<style scoped>
.sugs {
  border: 0;
  padding: 0;
  background: none;
  font: inherit;
  color: inherit;
  cursor: pointer;
  text-decoration: underline dotted;
  text-underline-offset: 3px;
}
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
