<script setup lang="ts">
import { roleNow } from '~/lib/replay'
// A text: the style bar, the page, the suggestions above the panel, and the counts along the bottom, inside the
// document window every app shares (DocumentFrame).
import { computed, nextTick, ref, watch } from 'vue'
import { DEFAULT_STYLE, SHAPE_LABEL_STYLE } from '@claudia/layout'
import { countWords } from '~/lib/paragraphs'
import { NEW_OBJECT_CAP, pictureSize, type PictureImport } from '~/lib/images'
import { pictureOf, useObjectClipboard } from '~/lib/object-clipboard'
import { NEW_OBJECT_WRAP, wrapAnnouncement, wrapLabel, wrapOf } from '~/lib/wrap'
import { toMarkdown } from '~/lib/markdown'
import { textStyleHost } from '~/lib/text-style-host'
import type { TextSession } from '~/lib/text-session'
import type { StyleView } from '~/lib/style-css'
import { formatItems } from '~/lib/format-menu'
import { hasHeadingStyles, headingsNumbered, type NumberingHost } from '~/lib/numbering'
import { looksOf, type ContentsHost } from '~/lib/contents'
import { usePageNumbers } from '~/lib/print/page-numbers'
import { SHOWS, type Show } from '~/lib/references'
import { showLabel } from '~/lib/reference-labels'
import {
  askItem,
  clipboardItems,
  preferencesMenu,
  darkItem,
  fileMenu,
  goToTargetItem,
  helpMenu,
  insertMenu,
  backItem, panelItem, referenceItem, replayItem,
  searchItem,
  undoRedoItems,
  type DocumentMenuContext,
} from '~/lib/document-menus'
import { chordLabel, chordOf, hintOf, searchShortcuts, type ShortcutDef } from '~/lib/shortcuts'
import { describeShortcut } from '~/lib/descriptions'
import { useNameAndDescribe } from '~/lib/use-name-and-describe'
import { insertTableItems, possible, tableItems, tableShortcuts, type TableAction, type TableMenuHost } from '~/lib/table-menu'
import { columnPlace, mergeRect, rowPlace } from '~/lib/tables'
import { marksFor, textSearchHost } from '~/lib/text-search-host'
import { useSearch } from '~/lib/use-search'
import { useI18n } from '~/lib/i18n'
import { useTheme } from '~/lib/theme'
import { remember, remembered } from '~/lib/storage'
import DocumentFrame from './DocumentFrame.vue'
import SearchPanel from './SearchPanel.vue'
import PrintPreview from './PrintPreview.vue'
import ImageImportDialog from './ImageImportDialog.vue'
import { textSource } from '~/lib/print/source'
import { usePrint } from '~/lib/print/use-print'
import { rotateItem } from '~/lib/rotate-menu'
import type { Menu, MenuItem } from './MenuBar.vue'

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
const dialog = ref<null | 'styles' | 'colours' | 'list-start' | 'numbering' | 'contents' | 'image' | 'table' | 'table-options'>(null)
const styleMenu = ref<{ x: number; y: number; mode?: 'edit' | 'apply' } | null>(null)
const styleHost = textStyleHost(session)
const active = ref<string | null>(null)
const editor = ref<{
  focus: () => void
  scrollToSuggestion: (id: string) => void
  scrollToParagraph: (id: string) => void
  caretPoint: () => { x: number; y: number }
  goTo: (target: string) => void
  syncCaret: () => void
} | null>(null)

// How I look at the text is mine alone (and is remembered in this browser).
const view = ref<'flow' | 'page'>(remembered('claudia.composes.view', ['flow', 'page'], 'flow'))
const authors = ref(remembered('claudia.composes.authors', ['on', 'off'], 'off') === 'on')
watch(view, (v) => remember('claudia.composes.view', v))
watch(authors, (on) => remember('claudia.composes.authors', on ? 'on' : 'off'))

// File ▸ Print… shows the pages in place of the text (D906, D918), as in every app that prints (`lib/print/use-print.ts`).
// (A new text's language, D915, is set by the server when it creates the document: UX-33.)
const { printing, preview, open: openPrint, close: closePrint, shortcut: PRINT } = usePrint(() => editor.value?.focus())
const printSource = textSource(session)

const readonly = computed(() => session.readOnly)
const words = computed(() => countWords(state.paragraphs))
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
  const order = state.paragraphs.map((b) => b.id)
  open.sort((a, b) => order.indexOf(a.paragraph) - order.indexOf(b.paragraph) || a.start - b.start)
  const at = after ? open.findIndex((s) => s.id === after) : -1
  const next = open[(at + 1) % Math.max(open.length, 1)]
  if (next) pick(next.id)
  else closeSuggestion()
}
function closeSuggestion() {
  opened.value = null
  active.value = null
}

/** File ▸ Export… (D212, D401): Markdown is built here from `state.paragraphs`, Word and OpenDocument text by the server. The window sends what is
 * still being typed before it opens the dialog (`DocumentFrame.openDialog`), so both see the text as it stands. */
const exportFormats = [
  { value: 'md', get label() { return t('Markdown (.md)') }, mimeType: 'text/markdown', local: () => toMarkdown(state.paragraphs, Object.values(state.styles)) },
  { value: 'docx', get label() { return t('Word document (.docx)') } },
  { value: 'odt', get label() { return t('OpenDocument text (.odt)') } },
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
/** Insert ▸ Container ▸ …: a container of the chosen type, hanging from the paragraph the caret is in (D560). */
async function addContainer(type: string) {
  const at = state.selection?.focus ?? (state.paragraphs[0] ? { paragraph: state.paragraphs[0].id, offset: 0 } : null)
  if (!at) return
  await session.addContainer(type, at, NEW_OBJECT_CAP)
}

/** Where the caret is, or the start of the text: what a new object hangs from. */
const hangFrom = () => state.selection?.focus ?? (state.paragraphs[0] ? { paragraph: state.paragraphs[0].id, offset: 0 } : null)
/** Edit ▸ Image…: a picture hangs from the character the caret is at, as a container does (E10.8, E10.16). It keeps its
 * own proportions, and is no bigger than 420 × 240 or the picture itself. The text stops above it and goes on below (D1061). */
function addPicture(picture: PictureImport, aspect: number): Promise<string | null> {
  const at = hangFrom()
  if (!at) return Promise.resolve(null)
  return session.addImage({ ...picture, fit: true }, at, pictureSize(aspect, NEW_OBJECT_CAP.h, NEW_OBJECT_CAP.w, picture.natural), NEW_OBJECT_WRAP)
}

const SHAPE_HEIGHT = 160
const TEXT_BOX = { w: 260, h: 100 }
/** Edit ▸ Text Box: an empty text box where the caret is (the same entry and key as in creates). */
async function addTextBox() {
  const at = hangFrom()
  if (at) await session.addTextBox(at, TEXT_BOX, NEW_OBJECT_WRAP)
}
/** Edit ▸ a shape of the library: it keeps its outline's proportions (a circle stays a circle). */
async function addShape(id: string) {
  const at = hangFrom()
  if (!at) return
  const aspect = (state.library.find((s) => s.id === id) ?? state.shapes[id])?.aspect ?? null
  await session.addShape(id, at, { w: Math.round(SHAPE_HEIGHT * (aspect ?? 1)), h: SHAPE_HEIGHT }, NEW_OBJECT_WRAP)
}

/** Format ▸ Wrap Text, Ctrl+Alt+R (D1064): the object selected goes on to the next way of letting the text flow round it,
 * and the status line says which one it is now, for those who cannot see the page. */
async function cycleWrap() {
  const id = state.selectedObject
  if (!id || readonly.value) return
  const now = await session.cycleWrap(id)
  if (now) session.notice(wrapAnnouncement(now), 'info')
}
const WRAP_TEXT: ShortcutDef = { id: 'format.wrap-text', get label() { return t('Wrap Text') }, chord: chordOf('format.wrap-text'), run: () => void cycleWrap(), enabled: () => !!state.selectedObject && !readonly.value && !printing.value }
/** What Wrap Text shows beside its name: the mode the selected object has now. */
const currentWrap = computed(() => (state.selectedObject && state.objects[state.selectedObject] ? wrapOf(state.objects[state.selectedObject]!.anchor).wrap : null))
function pictureInserted() {
  dialog.value = null
  nextTick(() => editor.value?.focus())
}

/** Cut, Copy and Paste of a picture (D1229): the same module as in the other two apps; a paste hangs it from the caret. */
const objectClip = useObjectClipboard({
  selected: () => {
    const id = state.selectedObject
    const o = id ? state.objects[id] : null
    return id && o ? { id, body: o, asset: o.ref ? state.images[o.ref] : undefined } : null
  },
  readonly: () => readonly.value,
  remove: (id) => session.removeObject(id),
  add: async (clip) => {
    const at = hangFrom()
    if (at) await session.addImage(pictureOf(clip), at, { w: clip.w, h: clip.h }, NEW_OBJECT_WRAP)
  },
})

async function pasteFromClipboard() {
  if (await objectClip.paste()) return
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

// ------------------------------------------------------------------------------ Search & replace (E9.28)
// The panel is one component for the three apps; this is the text's side of it: where it can look, how a match is named
// and gone to, and the marks the editor draws for what it found. Ctrl+F and Ctrl+H work anywhere in the window except in
// a text field of its own, which keeps the browser's find; what is selected in the text becomes the first thing to find.
const search = useSearch(() => !readonly.value, () => editor.value?.focus())
/** While replaying, a view that follows goes to the paragraph the step touched (E5.19, D551). */
watch(
  () => state.replay?.focus,
  (focus) => {
    if (!focus || !state.replay?.follow) return
    const first = focus.find((r) => r.kind === 'text')
    if (first?.kind === 'text') editor.value?.scrollToParagraph(first.paragraph)
  },
)
const searchHost = textSearchHost({ session, goTo: (paragraph) => editor.value?.scrollToParagraph(paragraph), t })
const searchMarks = computed(() => (search.open.value ? marksFor(search.view.value.matches, search.view.value.current) : []))
const openSearch = (replace = false) => search.openSearch(replace, session.selectedText())

// ------------------------------------------------------------------------------ menus and shortcuts
// D122: composes' one shortcut of its own, on top of the window's Undo, Redo and Save.
/** Format ▸ Name & describe…, Ctrl+Alt+D (D1317): the object selected, else the paragraph the caret is in. */
const nameDialog = useNameAndDescribe(session, () => editor.value?.focus())
function openDescribe() {
  if (readonly.value) return session.tellLookOnly()
  const id = state.selectedObject ?? state.selection?.focus.paragraph
  if (id) void nameDialog.open(id)
}
const DESCRIBE = describeShortcut(openDescribe, () => !readonly.value && !!(state.selectedObject ?? state.selection))
const LOOK: ShortcutDef = { id: 'format.look', get label() { return t('Edit This Style…') }, chord: chordOf('format.look'), run: () => openStyleMenu() }
// D912: a non-breaking hyphen says where a word may not be broken (as in Word and LibreOffice); its key stayed when
// its entry left the menu (the menu workbook, "Keys without entry"). The soft hyphen's entry and key were dropped.
const typing = () => !printing.value && !session.readOnly
const HARD_HYPHEN: ShortcutDef = { id: 'edit.nonbreaking-hyphen', get label() { return t('Non-breaking Hyphen') }, chord: chordOf('edit.nonbreaking-hyphen'), run: () => session.type('\u2011'), enabled: typing }
// E9.21: bullets and numbers, on the keys of the digits (Google Docs' Ctrl+Shift+8 and 7), whatever they type.
const BULLETS: ShortcutDef = { id: 'format.bulleted-list', get label() { return t('Bulleted List') }, chord: chordOf('format.bulleted-list'), run: () => makeList('bullets'), enabled: () => !readonly.value }
const NUMBERS: ShortcutDef = { id: 'format.numbered-list', get label() { return t('Numbered List') }, chord: chordOf('format.numbered-list'), run: () => makeList('numbers'), enabled: () => !readonly.value }
// E9.32: the keys of the table entries work in a box, which is a field of its own (`whileTyping`).
const tableHost: TableMenuHost = {
  get table() {
    return session.boxTable()
  },
  get box() {
    return state.box
  },
  get readonly() {
    return readonly.value || printing.value
  },
  run: (action) => void runTable(action),
}
const extraShortcuts = [
  LOOK,
  DESCRIBE,
  WRAP_TEXT,
  ...tableShortcuts({ t }, tableHost),
  PRINT,
  HARD_HYPHEN,
  BULLETS,
  NUMBERS,
  ...searchShortcuts({ find: () => openSearch(), replace: () => openSearch(true), canReplace: () => !readonly.value && !printing.value }),
]

// ------------------------------------------------------------------------------ tables (E9.32)
/** Where the menu of an object or a table is open (D1225, D1224), and a turn being tried from its Rotate By…. */
const objectMenu = ref<{ id: string; x: number; y: number } | null>(null)
const turning = ref<{ id: string; turn: number } | null>(null)
const objectMenuHost = ref<{ quarter: (direction: 1 | -1) => Promise<void>; openRotateBy: () => void } | null>(null)

/** The table whose options are open, and the column the caret was in. */
const optionsFor = ref<{ table: string; column?: string } | null>(null)

/** Insert ▸ Table…: the dialog asks how big; the table goes after the paragraph the caret is in. */
const canInsertTable = () => !readonly.value && !!state.selection && !state.box
/** Where the table goes: the caret as it was when the menu entry was chosen (the dialog takes the focus, and a click
 *  into its fields must not move the place). */
let tablePlace: { paragraph: string; offset: number } | null = null
function openTableDialog() {
  editor.value?.syncCaret()
  const focus = state.selection?.focus
  tablePlace = focus ? { paragraph: focus.paragraph, offset: focus.offset } : null
  dialog.value = 'table'
}
async function insertTable(size: { rows: number; cols: number; headerRows: number }) {
  dialog.value = null
  const place = tablePlace
  tablePlace = null
  if (!place) return
  const made = await session.addTable(place, size)
  if (!made) return
  await nextTick()
  document.querySelector<HTMLTextAreaElement>(`[data-object="${CSS.escape(made.object)}"] textarea`)?.focus()
}
function openTableOptions(table: string, column?: string) {
  optionsFor.value = { table, column }
  dialog.value = 'table-options'
}

/** What the table entries of Edit do, to the table and the box the caret is in. */
async function runTable(action: TableAction) {
  const table = session.boxTable()
  const box = state.box
  if (!table || !box || !possible(tableHost, action)) return
  switch (action) {
    case 'row-above':
    case 'row-below':
      await session.insertRows(table.id, rowPlace(box.row, action === 'row-above' ? 'above' : 'below'))
      break
    case 'row-delete':
      await session.deleteRows(table.id, [box.row])
      break
    case 'column-left':
    case 'column-right':
      await session.insertColumns(table.id, columnPlace(box.col, action === 'column-left' ? 'left' : 'right'))
      break
    case 'column-delete':
      await session.deleteColumns(table.id, [box.col])
      break
    case 'sort-ascending':
    case 'sort-descending':
      await session.sortRows(table.id, box.col, action === 'sort-descending')
      break
    case 'merge-cells': {
      const joined = mergeRect(table, box)
      if (joined) await session.mergeCells(table.id, joined.row, joined.col, joined.rows, joined.cols)
      break
    }
    case 'split-cell':
      await session.splitCell(table.id, box.row, box.col)
      break
    case 'options':
      openTableOptions(table.id, box.col)
      break
  }
}

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

/** What the numbering manager works with (E9.22): the text's books, and the session's requests. */
const numberingHost = computed<NumberingHost>(() => ({
  schemes: state.schemes,
  lists: state.lists,
  styles: Object.values(state.styles),
  readOnly: readonly.value,
  newScheme: (like, name) => session.newScheme(like, name),
  changeScheme: (scheme) => session.changeScheme(scheme),
  resetScheme: (scheme) => session.resetScheme(scheme),
  removeScheme: (scheme) => session.removeScheme(scheme),
}))

// ------------------------------------------------------------------------------ references (step H)
/** Insert ▸ Cross-Reference…: the picker at the caret. */
const picker = ref<{ x: number; y: number } | null>(null)
function openPicker() {
  picker.value = editor.value?.caretPoint() ?? { x: 200, y: 200 }
}
async function putReference(target: string, show: Show) {
  picker.value = null
  await session.insertReference(target, show)
  editor.value?.focus()
}
/** The reference at the caret: the one right after it, else the one right before it (or the selected one). */
function referenceAtCaret() {
  const sel = state.selection
  if (!sel) return null
  const at = sel.anchor.paragraph === sel.focus.paragraph ? Math.min(sel.anchor.offset, sel.focus.offset) : sel.focus.offset
  return session.referenceAt({ paragraph: sel.focus.paragraph, offset: at }) ?? (at > 0 ? session.referenceAt({ paragraph: sel.focus.paragraph, offset: at - 1 }) : null)
}
function goToTarget() {
  const found = referenceAtCaret()
  if (found && found.shown?.state !== 'broken') editor.value?.goTo(found.field.target)
}
/** A reference's own menu (mock-up C): Show As, Go to Target, Remove Reference. */
const refMenu = ref<{ paragraph: string; index: number; x: number; y: number } | null>(null)
const refMenuItems = computed<MenuItem[]>(() => {
  const at = refMenu.value
  const paragraph = at && state.paragraphs.find((b) => b.id === at.paragraph)
  const field = paragraph?.fields?.[at!.index]
  if (!at || !field) return []
  const shows = SHOWS.map((s) => ({ label: `${field.show === s ? '✓ ' : ''}${t('Show As')} ${showLabel(s)}`, disabled: readonly.value || field.show === s, action: () => void session.setFieldShow(at.paragraph, at.index, s) }))
  return [
    ...shows,
    { label: '', separator: true },
    { label: t('Go to Target'), hint: hintOf('edit.go-to-target'), disabled: paragraph.shown?.[at.index]?.state === 'broken', action: () => editor.value?.goTo(field.target) },
    { label: t('Remove Reference'), hint: 'Delete', disabled: readonly.value, action: () => void session.replaceSelection('') },
  ]
})

/** In Page view, the page each paragraph starts on, for the tables of contents (E9.31, step F). */
const pageNumbers = usePageNumbers(session, () => view.value === 'page' && !printing.value)

/** The table of contents whose options are open (E9.31), and what the dialog works with. */
const contentsOf = ref<string | null>(null)
const contentsHost = computed<ContentsHost | null>(() => {
  const paragraph = state.paragraphs.find((b) => b.id === contentsOf.value)
  if (!paragraph?.generated) return null
  return {
    paragraph: paragraph.id,
    options: paragraph.generated,
    entries: paragraph.entries ?? [],
    looks: looksOf(paragraph.entries ?? [], Object.values(state.styles)),
    readOnly: readonly.value,
    set: (options) => session.setContents(paragraph.id, options),
    remove: () => session.removeContents(paragraph.id),
  }
})
function openContents(paragraph: string) {
  contentsOf.value = paragraph
  dialog.value = 'contents'
}
/** Insert ▸ Table of Contents: one at the caret; with the caret on a table, its options (the mock-up's rule). */
function insertContents() {
  const on = session.currentContents()
  if (on) openContents(on.id)
  else void session.insertContents().then(() => editor.value?.focus())
}

/** What the shared menu items need from this window (`lib/document-menus.ts`). */
const shared = computed<DocumentMenuContext>(() => ({
  t,
  role: roleNow(state),
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
        { label: '', separator: true },
        searchItem(c, { open: () => openSearch() }),
        { label: '', separator: true },
        // the paragraph with the caret (D554); a floating object cannot be selected in the text yet
        referenceItem(c, { run: () => void frame.value?.referenceThing(session.state.selection?.focus.paragraph ?? ''), possible: () => !!session.state.selection }),
        goToTargetItem(c, { run: () => goToTarget(), possible: () => !!referenceAtCaret() }),
        { label: '', separator: true },
        // a picture hangs from the caret's character, like a container (E10.16); its key is the same in all three apps
        { id: 'edit.image', label: t('Image…'), action: () => (dialog.value = 'image'), disabled: readonly.value || !state.selection },
        { id: 'edit.text-box', label: t('Text Box'), action: () => void addTextBox(), disabled: readonly.value || !state.selection },
        // the outlines the server offers, as in creates; they hang from the caret's character like a picture
        ...state.library.map((s) => ({ label: s.name, action: () => void addShape(s.id), disabled: readonly.value || !state.selection })),
        { label: '', separator: true },
        // The two characters that had keys and no menu entry (UX-35/UX-36): where a word may break, and where never.
        {
          label: t('Insert'),
          disabled: !typing(),
          items: [
            { id: 'edit.nonbreaking-hyphen', label: t('Non-breaking Hyphen'), disabled: !typing(), action: () => HARD_HYPHEN.run() },
          ],
        },
      ],
    },
    insertMenu(c, { types: state.containerTypes, add: (type) => addContainer(type) }, { label: t('Table of Contents'), add: insertContents, possible: !readonly.value && !!state.selection }, { add: openPicker, possible: !readonly.value && !!state.selection }, insertTableItems(c, { add: openTableDialog, possible: canInsertTable() })),
    {
      label: t('Format'),
      items: [
        ...(Object.keys(state.styles).length === 0
          ? [{ label: t('No styles yet'), disabled: true }]
          : formatItems(t, {
              // D127's groups — structure · running text · called-out paragraphs — and then any style of the text's own.
              // Structure is every style that gives a heading level (E9.22), by its level: the title and the
              // headings, and any style somebody made a heading.
              groups: [headingStyles(), builtins([DEFAULT_STYLE.composes]), builtins(CALLED_OUT_STYLE_IDS), customStyles()],
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
                headings: {
                  label: t('Number Headings'),
                  on: headingsNumbered(Object.values(state.styles)),
                  possible: hasHeadingStyles(Object.values(state.styles)),
                  toggle: () => void session.numberHeadings(!headingsNumbered(Object.values(state.styles))),
                },
                allNumbering: () => (dialog.value = 'numbering'),
              },
            })),
        { label: '', separator: true },
        { id: 'format.describe', label: t('Name & describe…'), hint: chordLabel(DESCRIBE.chord), action: () => openDescribe(), disabled: readonly.value || !(state.selectedObject ?? state.selection) },
        { label: '', separator: true },
        // a quarter turn each way and any angle, for what turns (a chart and a table do not, D1021, D1224)
        rotateItem(t, {
          kind: () => (state.selectedObject ? (state.objects[state.selectedObject]?.kind ?? null) : null),
          readonly: () => readonly.value || printing.value,
          quarter: (direction) => void objectMenuHost.value?.quarter(direction),
          by: () => objectMenuHost.value?.openRotateBy(),
        }),
        { label: '', separator: true },
        // one entry and one key that cycles the four modes (D1064); it says which mode the selected object has now
        {
          id: 'format.wrap-text',
          label: currentWrap.value ? t('Wrap Text: {mode}', { mode: wrapLabel(currentWrap.value) }) : t('Wrap Text'),
          action: () => void cycleWrap(),
          disabled: readonly.value || !state.selectedObject,
        },
      ],
    },
    {
      label: t('View'),
      items: [
        { id: 'view.authors', label: t('Show Who Wrote What'), checked: authors.value, action: (x) => (authors.value = x ? x === 'on' : !authors.value) },
        panelItem(c, { open: () => frame.value?.isPanelOpen() ?? true, toggle: () => frame.value?.togglePanel() }),
        replayItem(c, { start: () => frame.value?.replayHistory(), possible: () => state.entries.length > 0 && state.status === 'open' }),
        backItem(c, { go: () => session.goBack(), possible: () => !!state.wayBack }),
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
        // the table the caret is in (E9.32): on only in one of its boxes. In Tools since D1229, as computes has its pivot
        // table there.
        { label: '', separator: true },
        ...tableItems(c, tableHost),
      ],
    },
    preferencesMenu(c, { current: locale.value, choose }),
    helpMenu(c, { ask, openHelp: (mode) => frame.value?.openHelp(mode) }),
  ]
})

/** The built-in styles of one of D127's groups (structure · running text · called-out paragraphs), by id, in order. */
function builtins(ids: string[]): StyleView[] {
  return ids.map((id) => state.styles[id]).filter((s): s is StyleView => !!s)
}
/** The styles that make a paragraph a heading, by their level: the title first. */
function headingStyles(): StyleView[] {
  return Object.values(state.styles)
    .filter((s) => s.heading !== null && s.heading !== undefined && forParagraphs(s))
    .sort((a, b) => a.heading! - b.heading!)
}
/** The built-in styles of the called-out paragraphs (D127), as composes' built-ins name them (`tests/test_style_ids_generated.py`
 * checks that each is one). */
const CALLED_OUT_STYLE_IDS = ['quote', 'remark', 'definition']
const BUILTIN_STYLE_IDS = new Set([DEFAULT_STYLE.composes, ...CALLED_OUT_STYLE_IDS])
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
const OBJECT_WORDS_STYLE_IDS = new Set([SHAPE_LABEL_STYLE])
const forParagraphs = (s: StyleView) => s.kind === 'paragraph' && !OBJECT_WORDS_STYLE_IDS.has(s.id)
/** A style made by deviating from a built-in (`next_style` in `model.py`) is not one of the three fixed groups above
 * — D127 only grouped the built-ins, so anything else gets its own trailing group rather than being folded silently
 * into one of them. A style that gives a heading level is in the structure group instead, whoever made it (E9.22). */
function customStyles(): StyleView[] {
  return Object.values(state.styles).filter((s) => !BUILTIN_STYLE_IDS.has(s.id) && (s.heading === null || s.heading === undefined) && forParagraphs(s))
}

// Preferences ▸ Shortcuts (D122/D126): the things that are not a `keydown` shortcut at all — typing itself, and native
// Ctrl+C/X/V, which the browser already handles for whatever has focus.
const SHORTCUT_NOTES = computed<[string, string][]>(() => [
  [t('Type'), t('write; a word is sent when it ends, and the others see where you are')],
  [t('Enter'), t('end the paragraph (after a heading the next one is body text); in a list, the next item; on an empty item, out of the list')],
  [t('Tab / Shift + Tab'), t('in a list, one level in or out')],
  [t('Backspace / Delete'), t('delete; at the edge of a paragraph it joins the one next to it')],
  [t('Ctrl + Backspace / Delete'), t('delete a word')],
  [t('Ctrl + C / X / V'), t('copy, cut and paste, also from and to other programs')],
  [t('@ai review this text'), t('the assistant suggests changes; you accept or reject each')],
])
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
      <StyleBar v-if="!printing" data-region="toolbar" :session="session" :view="view" :authors="authors" @view="view = $event" @authors="authors = $event" @styled="editor?.focus()" @look="openStyleMenu" />
    </template>
    <PrintPreview v-if="printing" ref="preview" :source="printSource" @close="closePrint" />
    <TextEditor v-else ref="editor" data-region="document" :session="session" :view="view" :authors="authors" :active="active" :marks="searchMarks" :pages="pageNumbers" :turning="turning" @suggestion="pick" @style-menu="openStyleMenu" @contents="openContents" @reference-menu="refMenu = $event" @table-options="openTableOptions" @object-menu="objectMenu = $event" />
    <template #footer>
      <footer v-if="!printing" class="foot">
        <div class="stats mono" aria-live="polite">
          <span><b data-testid="words">{{ words }}</b> {{ words === 1 ? t('word') : t('words') }}</span>
          <span><b>{{ state.paragraphs.length }}</b> {{ state.paragraphs.length === 1 ? t('paragraph') : t('paragraphs') }}</span>
          <button v-if="openSuggestions" type="button" class="sugs" data-testid="open-suggestions" :title="t('Open the first suggestion')" @click="pickNext()"><b>{{ openSuggestions }}</b> {{ openSuggestions === 1 ? t('suggestion') : t('suggestions') }}</button>
        </div>
        <span class="rev mono" :title="t('branch {branch}', { branch: state.branch })">{{ state.revision ?? t('empty') }}</span>
      </footer>
    </template>
    <template #overlay>
      <SearchPanel
        v-if="search.open.value"
        :ref="(panel) => (search.panel.value = panel as never)"
        :host="searchHost"
        :replace="search.replace.value"
        @close="search.closeSearch()"
        @view="search.view.value = $event"
        @help="frame?.openHelp('how-to', searchHost.helpTopic)"
      />
      <SuggestionPopover v-if="opened" :id="opened.id" :key="opened.id" :session="session" :x="opened.x" :y="opened.y" @close="closeSuggestion" @next="pickNext(opened.id)" />
      <StyleMenu v-if="styleMenu" :host="styleHost" :x="styleMenu.x" :y="styleMenu.y" :mode="styleMenu.mode" @close="closeStyleMenu" @styles="(styleMenu = null), (dialog = 'styles')" />
      <ImageImportDialog v-if="dialog === 'image'" :add="addPicture" @close="dialog = null" @inserted="pictureInserted" />
      <StylesDialog v-if="dialog === 'styles'" :host="styleHost" @close="dialog = null" />
      <ReferencePicker v-if="picker" :x="picker.x" :y="picker.y" :targets="(q) => session.referenceTargets(q)" @choose="putReference" @close="(picker = null), editor?.focus()" />
      <NameAndDescribeDialog v-if="nameDialog.details.value" :details="nameDialog.details.value" @save="nameDialog.save" @close="nameDialog.close" />
      <TextObjectMenu ref="objectMenuHost" :session="session" :menu="objectMenu" :table-host="tableHost" :clipboard="objectClip" @close="objectMenu = null" @turning="turning = $event" @styles="dialog = 'styles'" />
      <ContextMenu v-if="refMenu" :x="refMenu.x" :y="refMenu.y" :items="refMenuItems" :width="260" :label="t('Reference menu')" @close="refMenu = null" />
      <ContentsDialog v-if="dialog === 'contents' && contentsHost" :host="contentsHost" :title="t('Table of contents')" @close="dialog = null" />
      <NumberingDialog v-if="dialog === 'numbering'" :host="numberingHost" :initial="session.currentScheme() ?? undefined" @close="dialog = null" />
      <PromptDialog v-if="dialog === 'list-start'" :title="t('Start numbering at')" :label="t('First number')" :ok="t('Start')" required :initial="listStart()" @ok="startListAt" @close="dialog = null" />
      <TableDialog v-if="dialog === 'table'" @insert="insertTable" @close="dialog = null" />
      <TableOptionsDialog v-if="dialog === 'table-options' && optionsFor" :session="session" :table="optionsFor.table" :start-column="optionsFor.column" @close="(dialog = null), (optionsFor = null)" />
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
