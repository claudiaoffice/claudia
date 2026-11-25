<script setup lang="ts">
import { lookOnly } from '~/lib/replay'
// A presentation: the slide, the tool bar to put things on it, the slides along the bottom and the panel.
import { computed, nextTick, ref } from 'vue'
import { insertFrame } from '~/lib/geometry'
import type { PictureImport } from '~/lib/images'
import type { SlideSession } from '~/lib/slide-session'
import { pasteAsPlainText } from '~/lib/clipboard'
import type { Thing } from '~/lib/fits/facts'
import type { ContextMenuOf, Handler, Handlers } from '~/lib/menus/assemble'
import { useMenus, windowFacts } from '~/lib/menus/use-menus'
import { notYet, windowHandlers } from '~/lib/menus/window-handlers'
import { canTurn } from '~/lib/turning'
import { useI18n } from '~/lib/i18n'
import { objectStyleHost, type ObjectStyling } from '~/lib/object-style-host'
import { hintOf, searchShortcuts } from '~/lib/shortcuts'
import { looksOf, type ContentsHost } from '~/lib/contents'
import type { Show } from '~/lib/references'
import { hasHeadingStyles, headingsNumbered, type NumberingHost } from '~/lib/numbering'
import { useGrid } from '~/lib/grid'
import { marksFor, slideSearchHost } from '~/lib/slide-search-host'
import { useSearch } from '~/lib/use-search'
import { useTheme } from '~/lib/theme'
import { presentShortcuts } from '~/lib/present-keys'
import { useNotesShown } from '~/lib/show-prefs'
import { formatTime } from '~/lib/show-time'
import DocumentFrame from './DocumentFrame.vue'
import SlideCanvas from './SlideCanvas.vue'
import ImageImportDialog from './ImageImportDialog.vue'
import PrintPreview from './PrintPreview.vue'
import PresentShow from './PresentShow.vue'
import SlideNotes from './SlideNotes.vue'
import SearchPanel from './SearchPanel.vue'
import { slideSource } from '~/lib/print/source'
import { usePrint } from '~/lib/print/use-print'

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
const dialog = ref<null | 'styles' | 'colours' | 'rename' | 'list-start' | 'numbering' | 'agenda'>(null)
const EXPORT_FORMATS = [
  { value: 'pptx', get label() { return t('PowerPoint presentation (.pptx)') } },
  { value: 'odp', get label() { return t('OpenDocument presentation (.odp)') } },
]

const readonly = computed(() => lookOnly(state))

// ------------------------------------------------------------------------------ the show and the notes (E10.2)
// Presenting is read-only and local (D340): a viewer may do it too, and it writes nothing to the document.
const { shown: notesShown, toggle: toggleNotes } = useNotesShown()
const notes = ref<InstanceType<typeof SlideNotes> | null>(null)
const presenting = ref<{ from: number } | null>(null)
const plan = computed(() => session.plan())
function present(from: 'start' | 'here') {
  if (!state.slides.length || printing.value) return
  presenting.value = { from: from === 'start' ? 0 : Math.max(here.value, 0) }
}
function endShow() {
  presenting.value = null
  canvas.value?.focus()
}
/** Rename the slide shown, or the tab that was double-clicked (D550): a tag in the chat keeps pointing at it. */
const renaming = ref<{ id: string; name: string } | null>(null)
function askRename(id: string = state.activeSlide) {
  const index = state.slides.findIndex((x) => x.id === id)
  if (readonly.value || index < 0) return
  renaming.value = { id, name: session.slideLabel(id, index) }
  dialog.value = 'rename'
}
async function rename(name: string) {
  const target = renaming.value
  dialog.value = null
  renaming.value = null
  if (target && name !== target.name) await session.renameThing(target.id, name)
}
/** The time chip wants the notes field in view: shown if it was hidden. */
async function planTime() {
  if (readonly.value) return
  notesShown.value = true
  await nextTick()
  void notes.value?.openTime()
}

// File ▸ Print… shows the pages in place of the slide (D906, D918), as in every app that prints (`lib/print/use-print.ts`).
// (A new presentation's language, D915, D917, is set by the server when it creates the document: UX-33.)
const { printing, preview, open: openPrint, close: closePrint} = usePrint(() => canvas.value?.focus())
const printSource = slideSource(session)
// ------------------------------------------------------------------------------ Search & replace (E10.19)
// The panel is one component for the three apps; this is the presentation's side of it: where it can look (all slides,
// this slide), how a match is named and gone to, and the marks the slide draws for what it found in the words of its
// objects. Ctrl+F and Ctrl+H work anywhere in the window except in a text field of its own, which keeps the browser's find.
const search = useSearch(() => !readonly.value, () => canvas.value?.focus())
const searchHost = slideSearchHost({ session, showNotes: () => (notesShown.value = true), t })
const searchMarks = computed(() => (search.open.value ? marksFor(search.view.value.matches, search.view.value.current, state.activeSlide) : []))
const openSearch = (replace = false) => search.openSearch(replace)

// The keys with rules of their own (Ctrl+H; Present's letter keys beside F5, D344); every menu entry's key comes from
// the definition (`DocumentFrame`, D1604).
const extraShortcuts = [
  ...searchShortcuts({ find: () => openSearch(), replace: () => openSearch(true), canReplace: () => !readonly.value && !printing.value }),
  ...presentShortcuts(t, { start: () => present('start'), here: () => present('here') }),
]
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

/** What the numbering manager works with (E9.22): the presentation's books, and the session's requests. */
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
/** Insert ▸ Cross-Reference…: the picker at the selected box (its words are taken first when they are being edited). */
const picker = ref<{ id: string; offset: number; x: number; y: number } | null>(null)
async function openPicker() {
  const place = await canvas.value?.referencePlace()
  if (place) picker.value = place
  else session.notice(t('Select a text box or a shape with words to put a reference into.'), 'warning')
}
async function putReference(target: string, show: Show) {
  const place = picker.value
  picker.value = null
  if (place) await session.insertReference(place.id, place.offset, target, show)
}
/** Edit ▸ Go to Target: to the slide of what the selected box's reference points at, and select it there. */
async function goToTarget() {
  const found = state.selected ? session.referenceIn(state.selected) : null
  const target = found && found.shown?.state !== 'broken' ? state.objects[found.field.target] : undefined
  if (!target) return
  await session.showSlide(target.anchor.holder)
  await session.select(target.id)
}

/** The agenda whose options are open (E9.31), and what the dialog works with: no levels (the slide titles are one
 * level) and slide numbers in place of page numbers. Remove takes the text box away. */
const agendaOf = ref<string | null>(null)
const agendaHost = computed<ContentsHost | null>(() => {
  const id = agendaOf.value
  const options = id ? state.objects[id]?.paragraph?.generated : null
  if (!id || !options) return null
  const entries = session.agendaOf(id) ?? []
  return {
    paragraph: id,
    options,
    entries,
    looks: looksOf(entries, Object.values(state.styles)),
    readOnly: readonly.value,
    set: (next) => session.setContents(id, next),
    remove: () => session.removeObject(id),
  }
})
function openAgenda(id: string) {
  agendaOf.value = id
  dialog.value = 'agenda'
}
/** Insert ▸ Agenda: one on the slide shown; with an agenda selected, its options. */
function insertAgenda() {
  const selected = state.selected
  if (selected && state.objects[selected]?.paragraph?.generated) openAgenda(selected)
  else void session.insertAgenda()
}

const listStart = () => String(state.lists.find((l) => l.id === session.selectedItem()?.list)?.start ?? 1)
function startListAt(value: string) {
  const start = Number.parseInt(value, 10)
  if (Number.isInteger(start) && start >= 1 && start <= 999999) {
    void session.startAt(start)
    dialog.value = null
  }
}

/** Put the colours the document started with back, as the server itself states them (no second copy to drift). */
async function resetPalette() {
  const started = state.palette?.builtin ?? []
  if (started.length && (await session.replacePalette(started))) dialog.value = null
}
const here = computed(() => state.slides.findIndex((s) => s.id === state.activeSlide))
const count = computed(() => session.slideObjects(state.activeSlide).length)

async function addText() {
  if (await session.addText(insertFrame('text', null, count.value))) canvas.value?.focus()
}
async function addShape(id: string) {
  const outline = state.library.find((s) => s.id === id) ?? state.shapes[id]
  if (await session.addShape(id, insertFrame('shape', outline?.aspect ?? null, count.value))) canvas.value?.focus()
}
async function addContainer(type: string) {
  if (await session.addContainer(type, insertFrame('container', null, count.value))) canvas.value?.focus()
}
function addPicture(picture: PictureImport, aspect: number): Promise<string | null> {
  return session.addImage({ ...picture, fit: true }, insertFrame('image', aspect, count.value, picture.natural))
}
function imageInserted() {
  showImageDialog.value = false
  canvas.value?.focus()
}
async function remove() {
  if (state.selected) await session.removeObject(state.selected)
  canvas.value?.focus()
}

/** Copy/Cut act on the picture selected (D1229), else on whatever the browser still has selected; Paste puts a picture that
 * was cut or copied on the slide, else it only does anything while a text frame is in edit
 * mode (`document.activeElement` is then its contenteditable) — same honest limit `lib/clipboard.ts` documents: a
 * shape or an unselected canvas has no text to paste into, and the menu click quietly does nothing, same as a
 * native paste finding nowhere to land. */
async function pasteFromClipboard() {
  if (await canvas.value?.paste()) return // a picture that was cut or copied (D1229)
  await pasteAsPlainText(document.activeElement)
}

// ------------------------------------------------------------------------------ menus (D1644)
// The menus and context menus are the definition's (`menus.generated.ts`); what is true now says what fits (`fits/`),
// and these handlers say what each entry does here.
/** What is selected, for what fits (D1601): the object on the slide, with whether its words are a list's item. */
function selectionNow(): Thing[] {
  const o = state.selected ? state.objects[state.selected] : undefined
  if (!o) return []
  const holdsText = o.kind !== 'image' && o.kind !== 'chart'
  return [{ kind: 'object', holdsText, canTurn: canTurn(o.kind), onGrid: !!o.snap, listItem: holdsText && !!session.selectedItem() }]
}
const onSlide = () => (state.activeSlide ? null : t('Show a slide first.'))
const shape = (id: string): Handler => ({
  run: () => void addShape(id),
  notNow: () => (state.library.some((s) => s.id === id) ? null : t('This server offers no such shape.')),
})
const handlers = computed<Handlers>(() => ({
  ...windowHandlers({
    t,
    open: (name) => frame.value?.openDialog(name),
    leave: (opts) => emit('leave', opts),
    print: openPrint,
    history: { undo: () => session.undo(), redo: () => session.redo(), undoLabel: () => (state.canUndo ? state.undoLabel : ''), redoLabel: () => (state.canRedo ? state.redoLabel : '') },
    paste: () => void pasteFromClipboard(),
    search: () => openSearch(),
    panel: { open: () => frame.value?.isPanelOpen() ?? true, toggle: () => frame.value?.togglePanel() },
    replay: { start: () => frame.value?.replayHistory(), notNow: () => (state.entries.length > 0 && state.status === 'open' ? null : t('There is no history to replay yet.')) },
    back: () => session.goBack(),
    theme: { on: dark, toggle: toggleDark },
    ask: (text) => frame.value?.ask(text),
    help: (mode) => frame.value?.openHelp(mode),
    language: { current: () => locale.value, choose },
  }),
  'format.describe': { run: () => canvas.value?.openDescribe() },
  'edit.reference': { run: () => void frame.value?.referenceThing(state.selected ?? state.activeSlide) },
  'edit.go-to-target': { run: () => void goToTarget(), notNow: () => (state.selected && session.referenceIn(state.selected) ? null : t('There is no reference here.')) },
  'edit.rename-slide': { run: () => askRename(), notNow: onSlide },
  'edit.edit-text': { run: () => void canvas.value?.beginEdit() },
  'edit.delete': { run: () => void remove() },
  'edit.release-from-grid': { run: () => void (state.selected && session.setSnap?.(state.selected, false)) },
  'insert.cross-reference': { run: () => void openPicker() },
  'insert.contents': { run: () => insertAgenda(), notNow: onSlide },
  'edit.image': { run: () => (showImageDialog.value = true) },
  'edit.text-box': { run: () => void addText() },
  'insert.shape.circle': shape('circle'),
  'insert.shape.rectangle': shape('rectangle'),
  'insert.shape.triangle': shape('triangle'),
  ...Object.fromEntries(['latex', 'mermaid', 'typst'].map((type) => [`insert.container.${type}`, { run: () => void addContainer(type) }])),
  'edit.new-slide': { run: () => void session.addSlide() },
  'format.apply-style': { run: () => canvas.value?.openStyleMenu(undefined, 'apply') },
  'format.look': { run: () => canvas.value?.openStyleMenu() },
  'format.all-styles': { run: () => (dialog.value = 'styles') },
  'format.rotate-by': { run: () => canvas.value?.openRotateBy() },
  'format.bulleted-list': { run: () => void session.makeList('bullets'), checked: () => session.selectedScheme() === 'bullets' },
  'format.numbered-list': { run: () => void session.makeList('numbers'), checked: () => session.selectedScheme() === 'numbers' },
  'format.list-continue': { run: () => void session.continueList(), notNow: () => (session.canContinue() ? null : t('There is no list before this one to go on from.')) },
  'format.list-start': { run: () => (dialog.value = 'list-start') },
  'format.list-indent': { run: () => void session.indent(1) },
  'format.list-outdent': { run: () => void session.indent(-1) },
  'format.number-headings': {
    run: () => void session.numberHeadings(!headingsNumbered(Object.values(state.styles))),
    checked: () => headingsNumbered(Object.values(state.styles)),
    notNow: () => (hasHeadingStyles(Object.values(state.styles)) ? null : t('No style gives a heading level here.')),
  },
  'format.all-numbering': { run: () => (dialog.value = 'numbering') },
  'format.colours': { run: () => (dialog.value = 'colours') },
  'view.authors': notYet(t), // creates tracks no per-object authorship yet
  'view.grid': { run: () => toggleGrid(), checked: () => gridShown.value },
  'view.speaker-notes': { run: () => toggleNotes(), checked: () => notesShown.value },
  'view.present-here': { run: () => present('here'), notNow: () => (state.slides.length ? null : t('There is no slide to show.')) },
  'view.present-start': { run: () => present('start'), notNow: () => (state.slides.length ? null : t('There is no slide to show.')) },
  'edit.slide-time': { run: () => void planTime(), notNow: onSlide },
}))

const menus = useMenus('creates', {
  handlers: () => handlers.value,
  facts: () => windowFacts(state, { selection: selectionNow(), slides: state.slides.length, references: true, desktop: frame.value?.inDesktopApp() }),
  notice: (why) => session.notice(why, 'info'),
})
/** A context menu of this window: what fits the thing pressed, by the definition. */
const menuOf: ContextMenuOf = (id, own) => menus.value.context(id, own)

/** A right press on a slide's tab: the slide is shown, and its menu opens, the same as the slide's own (D1619). */
const tabMenu = ref<{ x: number; y: number; id: string } | null>(null)
async function openTabMenu(event: MouseEvent, id: string) {
  await session.showSlide(id)
  tabMenu.value = { x: event.clientX, y: event.clientY, id }
}
const tabMenuItems = computed(() =>
  tabMenu.value ? menuOf('tab', { 'format.describe': { run: () => canvas.value?.describeSlide() }, 'edit.reference': { run: () => void frame.value?.referenceThing(tabMenu.value?.id ?? '') } }) : [],
)

/** Preferences ▸ Shortcuts: the slide's own mouse and keyboard conventions, which are not a single key chord. */
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
        :present-hint="hintOf('view.present-start')"
        :present-label="t('Present')"
        @present="present('start')"
        @text="addText"
        @shape="addShape"
        @image="showImageDialog = true"
        @remove="remove"
        @undo="session.undo()"
        @redo="session.redo()"
      >
        <!-- Applying a style where composes and computes have it (owner's report, 2026-11-12): the popover only shows a
             style's look (UX-14), so without this a named style could be applied only from Format ▸ Apply style. -->
        <StylePicker :host="styleHost" :hint="hintOf('format.look')" @look="canvas?.openStyleMenu()" @styled="canvas?.focus()" />
        <StylePicker v-if="selectedKind === 'shape'" :host="labelHost" :caption="t('Label')" testid="label-picker" @look="canvas?.openStyleMenu()" @styled="canvas?.focus()" />
      </InsertBar>
    </template>
    <PrintPreview v-if="printing" ref="preview" :source="printSource" @close="closePrint" />
    <div v-else-if="state.activeSlide" class="stage">
      <SlideCanvas ref="canvas" class="canvas" data-region="document" :menu-of="menuOf" :session="session" :show-grid="gridShown" :marks="searchMarks" @styles="dialog = 'styles'" @agenda="openAgenda" />
      <SlideNotes v-if="notesShown" ref="notes" :session="session" :hint="hintOf('edit.slide-time')" :t="t" @present="present" />
    </div>
    <div v-else class="noslide">{{ t('This presentation has no slide.') }}</div>
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
      <PresentShow v-if="presenting" :session="session" :from="presenting.from" view="audience" :t="t" @close="endShow" />
      <ImageImportDialog v-if="showImageDialog" :add="addPicture" @close="showImageDialog = false" @inserted="imageInserted" />
      <PromptDialog v-if="dialog === 'rename' && renaming" :title="t('Rename slide')" :label="t('Name')" :ok="t('Rename')" required :initial="renaming.name" @ok="rename" @close="dialog = null" />
      <StylesDialog v-if="dialog === 'styles'" :host="styleHost" @close="dialog = null" />
      <ReferencePicker v-if="picker" :x="picker.x" :y="picker.y" :targets="(q) => session.referenceTargets(q)" @choose="putReference" @close="picker = null" />
      <ContentsDialog
        v-if="dialog === 'agenda' && agendaHost"
        :host="agendaHost"
        :title="t('Agenda')"
        :levels="false"
        :places-label="t('Slide numbers')"
        :places-note="t('after each title')"
        @close="dialog = null"
      />
      <NumberingDialog v-if="dialog === 'numbering'" :host="numberingHost" :initial="session.selectedScheme() ?? undefined" @close="dialog = null" />
      <PromptDialog v-if="dialog === 'list-start'" :title="t('Start numbering at')" :label="t('First number')" :ok="t('Start')" required :initial="listStart()" @ok="startListAt" @close="dialog = null" />
      <ContextMenu v-if="tabMenu" :x="tabMenu.x" :y="tabMenu.y" :items="tabMenuItems" :label="t('Slide menu')" @close="tabMenu = null" />
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
            :data-thing="s.id"
            :aria-selected="s.id === state.activeSlide"
            :class="{ on: s.id === state.activeSlide }"
            :title="readonly ? undefined : t('Double-click to rename')"
            @click="session.showSlide(s.id)"
            @dblclick="askRename(s.id)"
            @contextmenu.prevent="openTabMenu($event, s.id)"
          >
            {{ session.slideLabel(s.id, i) }}<span v-if="session.secondsOf(s.id) !== null" class="time mono">{{ formatTime(session.secondsOf(s.id)!) }}</span>
          </button>
          <button v-if="!readonly" type="button" class="add" :title="t('New Slide')" :aria-label="t('new slide')" @click="session.addSlide()">+</button>
        </div>
        <div class="stats mono">
          <span v-if="here >= 0">{{ here + 1 }} / {{ state.slides.length }}</span>
          <span v-if="plan.planned" class="plan" data-testid="plan-total" :title="t('The planned times of the slides, added up')">
            {{ t('Planned {time}', { time: formatTime(plan.seconds) }) }}<template v-if="plan.unplanned"> · {{ t('{n} without a time', { n: plan.unplanned }) }}</template>
          </span>
          <span class="rev" :title="t('branch {branch}', { branch: state.branch })">{{ state.revision ?? t('empty') }}</span>
        </div>
      </footer>
    </template>
  </DocumentFrame>
</template>

<style scoped>
.stage {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
}
.canvas {
  flex: 1;
}
.time {
  margin-inline-start: 8px;
  font-size: 11px;
  opacity: 0.7;
}
.plan {
  color: var(--ink);
}
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
