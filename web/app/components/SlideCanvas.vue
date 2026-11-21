<script setup lang="ts">
import { usePointed } from '~/lib/pointed'
import { lookOnly } from '~/lib/replay'
import { viewTints } from '~/lib/replay-tint'
// The slide on screen: its objects, and what people do to them. A click selects (and holds) an object, dragging moves
// it, the handles resize it, a double click or Enter edits its text, Delete removes it, and a right click offers the
// same "Edit text"/"Delete" at the point clicked rather than letting the browser's own menu show through. A handle above
// the selection turns it (D1024); a turned object is drawn turned about the centre of its frame. Nothing is
// believed until the server says so: while the pointer is down the frame is a preview here, committed on pointer up.
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { pictureOf as clippedImport, useObjectClipboard } from '~/lib/object-clipboard'
import { CORNERS, GRID_SIZE, HANDLES, SLIDE_BOUNDS, SLIDE_H, SLIDE_W, besideRect, insertFrame, fitScale, moveFrame, toSlide, NUDGE, NUDGE_FINE, type Frame, type Handle } from '~/lib/geometry'
import { gridOf } from '~/lib/object-gestures'
import { useObjectInteraction } from '~/lib/object-interaction'
import { objectName } from '~/lib/descriptions'
import { useNameAndDescribe } from '~/lib/use-name-and-describe'
import { canTurn, degreesText, moveTurned, quarterTurn, stepTurn, SHIFT_STEP } from '~/lib/turning'
import { imageDataUrl } from '~/lib/images'
import { cssOf as computedCss, pointer, slideFrame, wordsCssOf, wordsOf } from '~/lib/objects'
import { contextMenuItems } from '~/lib/object-menu'
import { objectStyleHost } from '~/lib/object-style-host'
import { colorOf, inkOn } from '~/lib/people'
import { facetCss, scaleCss } from '~/lib/slide-style'
import { withDisplayInk } from '~/lib/style-css'
import type { SlideObject, SlideSession } from '~/lib/slide-session'
import type { MenuItem } from './MenuBar.vue'
import { useI18n } from '~/lib/i18n'
import type { SlideMark } from '~/lib/slide-search-host'
import { renderedView } from '~/lib/rendering'

const { t } = useI18n()

// `showGrid` is the View menu's own preference (`lib/grid.ts`'s `useGrid`, held by SlideWorkspace.vue so the
// menu item and this canvas share the one choice) — whether the lines are drawn. It never gates snapping: an
// object snaps or not by its own `snap` field, grid lines shown or not (E10.15).
const props = defineProps<{ session: SlideSession; showGrid: boolean; marks?: SlideMark[] }>()
/** `styles` asks the workspace to open the all-styles dialog, which owns the modal layer. */
const emit = defineEmits<{ styles: []; agenda: [id: string] }>()
const session = props.session
const state = session.state

/** Cut, Copy and Paste of a picture (D1229): one module for the three apps. A paste puts the picture where a new one goes,
 * at the size it had (and no further out than the slide). */
const clip = useObjectClipboard({
  selected: () => {
    const o = state.selected ? state.objects[state.selected] : null
    return o ? { id: o.id, body: o, asset: o.ref ? state.images[o.ref] : undefined } : null
  },
  readonly: () => session.readOnly,
  remove: (id) => session.remove(id),
  add: async (c) => {
    const w = Math.min(c.w, SLIDE_W)
    const h = Math.min(c.h, SLIDE_H)
    const at = insertFrame('image', c.w / c.h, session.objectsOn(state.activeSlide).length)
    await session.addImage(clippedImport(c), { x: Math.max(0, Math.min(at.x, SLIDE_W - w)), y: Math.max(0, Math.min(at.y, SLIDE_H - h)), w, h })
  },
})
/** What a replay marks on this slide (D553): by object, what the step changed or what changed after it. */
const tints = computed(() => viewTints(state))
const replayClass = (id: string) => {
  const tint = tints.value.object(id)
  return tint && `replay-${tint}`
}

const MARGIN = 24
/** Screen pixels from the top edge of an object to the middle of its turn handle (the stem is 22, the hit area 32). */
const HANDLE_REACH = 38

const area = ref<HTMLElement | null>(null)
const slideEl = ref<HTMLElement | null>(null)
const editor = ref<{ focus(): void; take(): string; caretOffset(): number } | null>(null)
const size = ref({ w: 1200, h: 700 })
const scale = computed(() => fitScale(size.value, MARGIN))
const readonly = computed(() => lookOnly(state))
usePointed(state, area, (id) => `[data-id="${CSS.escape(id)}"]`)

const objects = computed(() => session.objectsOn(state.activeSlide))
/** What a search found in the words of an object (E10.19), to draw there. */
const marksOf = (id: string) => (props.marks ?? []).filter((m) => m.object === id)
const others = computed(() => session.selectedByOthers(state.activeSlide))

// ------------------------------------------------------------------------------ the screen scale
let watcher: ResizeObserver | null = null
onMounted(() => {
  if (!area.value) return
  const measure = () => (size.value = { w: area.value!.clientWidth, h: area.value!.clientHeight })
  measure()
  watcher = new ResizeObserver(measure)
  watcher.observe(area.value)
})
onBeforeUnmount(() => watcher?.disconnect())

// ------------------------------------------------------------------------------ how objects look
const px = (units: number) => `${Math.round(units * scale.value * 100) / 100}px`

/** The grid lines, drawn with a CSS background rather than one element per line; absent entirely when hidden,
 * so the slide prints and exports (D123, once that exists) exactly as it is without it. */
const gridStyle = computed(() => (props.showGrid ? { backgroundSize: `${px(GRID_SIZE)} ${px(GRID_SIZE)}` } : {}))

/** Where an object is on the screen; a frame being dragged replaces the one the server knows. */
function frameOf(o: SlideObject): Frame {
  return interaction.frameOf(o.id) ?? slideFrame(o)
}
/** How far an object is turned on the screen: the turn being tried while the handle or Rotate By… is at work, else its own. */
function rotationOf(o: SlideObject): number {
  return interaction.rotationOf(o.id) ?? o.rotation
}
const turnCss = (degrees: number) => (degrees ? { transform: `rotate(${degrees}deg)` } : {})
function boxStyle(o: SlideObject) {
  const f = frameOf(o)
  return { left: px(f.x), top: px(f.y), width: px(f.w), height: px(f.h), ...turnCss(rotationOf(o)) }
}
function cssOf(o: SlideObject) {
  // withDisplayInk: a text object's default ink, genuinely black in the document (D28/2026-11-06), still needs to
  // read against a dark slide canvas in dark mode — display-only, same fix as composes' paragraphCss.
  return withDisplayInk(scaleCss(computedCss(state.styles, o), scale.value))
}
/** The look of an object's words: its paragraph's style, not the object's own (D304, D310). */
function wordsCss(o: SlideObject) {
  return withDisplayInk(scaleCss(wordsCssOf(state.styles, o), scale.value))
}
function outline(o: SlideObject) {
  const shape = pointer(o, 'shape')
  return shape ? (state.shapes[shape] ?? null) : null
}
function textBox(o: SlideObject) {
  const area = outline(o)?.text_area ?? { x: 0, y: 0, w: 100, h: 100 }
  const pad = o.kind === 'text' ? 0 : 8 // a shape's text is not written right up to its edge
  const f = frameOf(o)
  return {
    left: `calc(${(area.x / 100) * f.w * scale.value}px + ${pad * scale.value}px)`,
    top: `calc(${(area.y / 100) * f.h * scale.value}px + ${pad * scale.value}px)`,
    width: `calc(${(area.w / 100) * f.w * scale.value}px - ${2 * pad * scale.value}px)`,
    height: `calc(${(area.h / 100) * f.h * scale.value}px - ${2 * pad * scale.value}px)`,
  }
}
/** Each slot draws only the facets it reads (D304), by the server's own table (`style_model`): the words their
 * text and paragraph, a text box's box its box, a shape's outline its paint. */
const facets = computed(() => state.styleModel?.facets)
function words(o: SlideObject): Record<string, string> {
  return facetCss(wordsCss(o), facets.value, ['text', 'paragraph'])
}
/** A text box's box — background, padding, a border per side (D310); a shape's box is its outline instead. */
function frameCss(o: SlideObject): Record<string, string> {
  return o.kind === 'text' ? { ...facetCss(cssOf(o), facets.value, ['box']), 'box-sizing': 'border-box' } : {}
}
function paintCss(o: SlideObject): Record<string, string> {
  return facetCss(cssOf(o), facets.value, ['outline'])
}
function textStyle(o: SlideObject): Record<string, string> {
  const centered = o.kind === 'shape'
  return { ...words(o), ...frameCss(o), display: 'flex', 'flex-direction': 'column', 'justify-content': centered ? 'center' : 'flex-start', ...textBox(o) }
}
function editorStyle(o: SlideObject): Record<string, string> {
  return { ...words(o), ...frameCss(o), ...textBox(o) }
}
function pictureOf(o: SlideObject) {
  const image = pointer(o, 'image')
  return image ? (state.images[image] ?? null) : null
}
/** The `<img>` source for an image object's picture, or '' before the asset has loaded (`images`/`objects`'s own
 * event may arrive in either order on first load). */
function pictureSrc(o: SlideObject): string {
  const asset = pictureOf(o)
  return asset ? imageDataUrl(asset) : ''
}
/** What a rendered container shows: its picture or why there is none yet (D560). */
const faceOf = (o: SlideObject) => renderedView(state, o, imageDataUrl)
/** The container whose text is being written, if any: it has an editor of its own (`RenderedEditor.vue`). */
const containerEditing = ref<string | null>(null)
async function commitContainer(o: SlideObject, text: string) {
  containerEditing.value = null
  area.value?.focus({ preventScroll: true })
  const rendering = pointer(o, 'rendered')
  if (rendering) await session.setRenderingSource(rendering, text)
}
function cancelContainer() {
  containerEditing.value = null
  area.value?.focus({ preventScroll: true })
}
/** What a screen reader says for an object: its kind and its description (or its words), or that it is decoration. */
const label = (o: SlideObject) => objectName(o, { shape: outline(o)?.name, words: wordsOf(o) })

// ------------------------------------------------------------------------------ selection, dragging, resizing
/** What a press and a drag do is `lib/object-interaction.ts`'s, the same in all three apps (D1221); this is what
 * creates tells it about its slide. */
const interaction = useObjectInteraction({
  get bounds() {
    return SLIDE_BOUNDS
  },
  get scale() {
    return scale.value
  },
  get readonly() {
    return readonly.value
  },
  toUnits: (event) => point(event),
  subject(id) {
    const o = state.objects[id]
    return o ? { id, frame: slideFrame(o), rotation: o.rotation, aspect: aspectOf(o), grid: gridOf(o.snap) } : null
  },
  async commit(change) {
    if (change.kind === 'move') return session.move(change.id, change.x, change.y)
    if (change.kind === 'resize') return session.resize(change.id, change.frame)
    return session.rotate(change.id, change.rotation)
  },
})
/** A turn being tried from Rotate By… (open to Done): a ref, so the template unwraps it. */
const { rotatePreview } = interaction
/** What a screen reader is told about a turn: the angle it has now. */
const turnSaid = ref('')

const selected = computed(() => (state.selected ? (state.objects[state.selected] ?? null) : null))
const selectedFrame = computed(() => (selected.value ? frameOf(selected.value) : null))
/** An image always keeps its own proportions, the same way a shape with a fixed `aspect` does (the server
 * refuses a `resize_object` that would not keep it, `claudia_creates._check_visual`). */
function aspectOf(o: SlideObject): number | null {
  if (o.kind === 'image') {
    const asset = pictureOf(o)
    return asset ? asset.width / asset.height : null
  }
  return outline(o)?.aspect ?? null
}
/** The turn handle is for an object that turns (not a chart), when it can be changed and is not being written in. */
const turnable = computed(() => {
  const o = selected.value
  return !!o && canTurn(o.kind) && !readonly.value && !editing.value && !containerEditing.value
})
const selectedTurn = computed(() => (selected.value ? rotationOf(selected.value) : 0))
/** Where the handle would be is off the slide (an object at the top edge, say): it goes to the other side of the object
 * instead, so it can always be reached. The stem and the chip go with it. */
const handleBelow = computed(() => {
  const f = selectedFrame.value
  if (!f) return false
  const radians = (selectedTurn.value * Math.PI) / 180
  const reach = (f.h * scale.value) / 2 + HANDLE_REACH
  const x = (f.x + f.w / 2) * scale.value + reach * Math.sin(radians)
  const y = (f.y + f.h / 2) * scale.value - reach * Math.cos(radians)
  const edge = 16
  return x < edge || y < edge || x > SLIDE_W * scale.value - edge || y > SLIDE_H * scale.value - edge
})
const handles = computed<Handle[]>(() => {
  const o = selected.value
  if (!o || readonly.value || editing.value || containerEditing.value) return []
  return aspectOf(o) !== null ? CORNERS : HANDLES
})

function point(event: { clientX: number; clientY: number }) {
  const box = slideEl.value!.getBoundingClientRect()
  return toSlide(event.clientX, event.clientY, box, scale.value)
}

async function onObjectDown(event: PointerEvent, o: SlideObject) {
  if (event.button !== 0) return
  event.stopPropagation()
  if (editing.value && editing.value.id === o.id) return
  const target = event.currentTarget as HTMLElement
  target.setPointerCapture(event.pointerId)
  await commitEdit()
  area.value?.focus({ preventScroll: true })
  interaction.begin(o.id, 'move', event)
  session.select(o.id)
}

function onHandleDown(event: PointerEvent, handle: Handle) {
  const o = selected.value
  if (!o || event.button !== 0) return
  event.stopPropagation()
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  interaction.begin(o.id, handle, event)
}

function onPointerMove(event: PointerEvent) {
  interaction.move(event)
}

/** The release: one change (a move, a resize or a turn) is sent, and what was tried stays on screen until the answer is in. */
async function onPointerUp() {
  const change = await interaction.release()
  if (change?.kind === 'rotate') turnSaid.value = t('Turned to {degrees}', { degrees: degreesText(change.rotation) })
}

// ------------------------------------------------------------------------------ turning (D1021, D1024)
function onTurnDown(event: PointerEvent) {
  const o = selected.value
  if (!o || !turnable.value || event.button !== 0) return
  event.stopPropagation()
  event.preventDefault() // the handle keeps no focus of its own from the mouse; the slide keeps it, so Esc reaches it
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  interaction.begin(o.id, 'turn', event)
}
/** Esc: drop the turn or drag that is being tried, and the object is as it was. */
function cancelTurn(): boolean {
  rotating.value = null
  return interaction.cancel()
}

/** The arrow keys on the handle: a degree, with Shift 15° (and the same keys turn it back). */
async function onTurnKey(event: KeyboardEvent) {
  const o = selected.value
  if (!o || !turnable.value) return
  const by: Record<string, number> = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }
  let to: number | null = null
  if (by[event.key] !== undefined) to = stepTurn(o.rotation, by[event.key]! * (event.shiftKey ? SHIFT_STEP : 1))
  else if (event.key === 'Home') to = 0
  if (to === null) return
  event.preventDefault()
  event.stopPropagation()
  if (to !== o.rotation && (await session.rotate(o.id, to))) turnSaid.value = t('Turned to {degrees}', { degrees: degreesText(state.objects[o.id]?.rotation ?? to) })
}

/** Format ▸ Rotate ▸ Rotate Right 90° / Rotate Left 90°, and the same two in the context menu. */
async function quarter(direction: 1 | -1, id: string | null = state.selected) {
  const o = id ? state.objects[id] : null
  if (!o || !canTurn(o.kind)) return
  if (readonly.value) return session.notice(t('You can only look at this document.'), 'warning')
  if (await session.rotate(o.id, quarterTurn(o.rotation, direction))) turnSaid.value = t('Turned to {degrees}', { degrees: degreesText(state.objects[o.id]?.rotation ?? 0) })
}

/** Rotate By…: the popover, beside the object. Its angles are previews on the slide until Done. */
const rotating = ref<{ id: string; x: number; y: number } | null>(null)
function openRotateBy(id: string | null = state.selected, at?: { x: number; y: number }) {
  const o = id ? state.objects[id] : null
  if (!o || !canTurn(o.kind)) return
  if (readonly.value) return session.notice(t('You can only look at this document.'), 'warning')
  const el = area.value?.querySelector(`[data-id="${CSS.escape(o.id)}"]`)
  const where = at ?? (el ? besideRect(el.getBoundingClientRect(), 264, window.innerWidth) : { x: 120, y: 160 })
  session.select(o.id)
  if (!interaction.startRotateBy(o.id)) return
  rotating.value = { id: o.id, ...where }
}
function previewTurn(angle: number) {
  if (rotating.value) interaction.previewRotateBy(angle)
}
async function doneRotateBy(angle: number) {
  rotating.value = null
  const change = await interaction.finishRotateBy(angle)
  if (change?.kind === 'rotate') turnSaid.value = t('Turned to {degrees}', { degrees: degreesText(angle) })
  area.value?.focus({ preventScroll: true })
}
function cancelRotateBy() {
  cancelTurn()
  area.value?.focus({ preventScroll: true })
}

/** A press on the slide itself, not on an object: nothing is selected any more. */
async function onSlideDown(event: PointerEvent) {
  if (event.button !== 0) return
  await commitEdit()
  area.value?.focus({ preventScroll: true })
  session.select(null)
}

// ------------------------------------------------------------------------------ right-click context menu
/** The object a right click opened the menu for, and where — not necessarily `selected`'s object once a second
 * right click lands on a different one while the first's menu is still fading, so this is tracked on its own. */
const contextMenu = ref<{ x: number; y: number; id: string } | null>(null)
const contextItems = computed<MenuItem[]>(() => {
  const o = contextMenu.value ? state.objects[contextMenu.value.id] : null
  if (!o) return []
  // The list is `lib/object-menu.ts`'s, one for all three apps (D1225); creates has the grid and no wrap.
  return contextMenuItems(
    o,
    readonly.value,
    {
      describe: () => {
        contextMenu.value = null
        openDescribe(o.id)
      },
      edit: () => beginEdit(o.id),
      style: () => {
        const at = contextMenu.value
        contextMenu.value = null
        styleMenu.value = at ? { x: at.x, y: at.y } : { x: 120, y: 160 }
      },
      rotateBy: () => {
        const at = contextMenu.value
        contextMenu.value = null
        openRotateBy(o.id, at ? { x: at.x, y: at.y } : undefined)
      },
      remove: () => session.remove(o.id),
      cut: () => void clip.cut(),
      copy: () => void clip.copy(),
      setSnap: (snap) => session.setSnap(o.id, snap),
    },
    { grid: true },
  )
})

// ------------------------------------------------------------------------------ the style menu (E9.7, D203)
/** Where the style menu is open, if it is. The menu itself is the one every app uses; what it styles is whatever
 * `objectStyleHost` says is selected, so this component only has to say where to put it. */
const styleMenu = ref<{ x: number; y: number; mode?: 'edit' | 'apply' } | null>(null)
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
})

/** Format ▸ Edit this style…, Apply style… and Shift+F10: beside the selected object, so it stays in view. */
function openStyleMenu(at?: { x: number; y: number }, mode: 'edit' | 'apply' = 'edit') {
  if (!state.selected) return
  const el = area.value?.querySelector(`[data-id="${CSS.escape(state.selected)}"]`)
  const where = at ?? (el ? besideRect(el.getBoundingClientRect(), mode === 'apply' ? 280 : 360, window.innerWidth) : { x: 120, y: 160 })
  styleMenu.value = { ...where, mode }
}
/** A picture's properties are reached from its Style… (D1225, workbook "To decide" #13), not from an entry of their own. */
const pictureProperties = computed(() => {
  const o = selected.value
  return o?.kind === 'image'
    ? () => {
        styleMenu.value = null
        propertiesFor.value = o.id
      }
    : undefined
})
function closeContextMenu() {
  contextMenu.value = null
}

// ------------------------------------------------------------------------------ image properties dialog
/** The image a right-click's "Properties" opened the dialog for (follow-up, 2026-11-07) — tracked separately from
 * `contextMenu`/`selected` since the menu itself has already closed by the time the dialog is showing. */
const propertiesFor = ref<string | null>(null)
const propertiesObject = computed(() => (propertiesFor.value ? state.objects[propertiesFor.value] ?? null : null))
// ------------------------------------------------------------------------------ describing an object (BITV 1.1.1)
/** Name & describe… (D1317): Format ▸ Name & describe…, Ctrl+Alt+D, or the context menu's "Name & describe…". The state
 * is kept here, since the context menu has closed by the time the dialog shows. */
const nameDialog = useNameAndDescribe(session, () => area.value?.focus({ preventScroll: true }))
function openDescribe(id: string | null = state.selected) {
  if (!id || !state.objects[id]) return
  if (readonly.value) return session.notice(t('You can only look at this document.'), 'warning')
  void nameDialog.open(id)
}

/** Was showing the browser's own menu here (Back, Inspect, …) over a shape, a text box or a picture — the bug
 * this fixes. Shift + right button still gets the browser's own menu, the same escape hatch `TextEditor.vue`'s
 * `onContextMenu` already gives composes, and editing text keeps its own menu too (spelling, …), same as before. */
function onObjectContext(event: MouseEvent, o: SlideObject) {
  if (event.shiftKey || editing.value?.id === o.id) return
  event.preventDefault()
  session.select(o.id)
  contextMenu.value = { x: event.clientX, y: event.clientY, id: o.id }
}

// ------------------------------------------------------------------------------ editing text
const editing = ref<{ id: string; text: string } | null>(null)
const setEditor = (el: unknown) => {
  editor.value = (el as { focus(): void; take(): string; caretOffset(): number } | null) ?? null
}

async function beginEdit(id: string | null = state.selected) {
  const o = id ? state.objects[id] : null
  if (!o || editing.value || containerEditing.value || o.kind === 'image') return // a picture has no text to write
  if (readonly.value) return session.notice(t('You can only look at this document.'), 'warning')
  await session.select(o.id)
  if (state.selected !== o.id) return // a colleague holds it
  if (o.kind === 'rendered') {
    containerEditing.value = o.id // its text is the definition's, in an editor of its own
    return
  }
  if (o.paragraph?.generated) {
    emit('agenda', o.id) // an agenda has no words to type (E9.31): its options open instead
    return
  }
  editing.value = { id: o.id, text: wordsOf(o) }
  await nextTick()
  editor.value?.focus()
}

/** Take the words of the editor (`text`, or what it holds now for a press elsewhere) as typing: only what differs
 * from the box's words is written, so the rest keeps its writer (step G). */
async function commitEdit(text?: string) {
  const e = editing.value
  if (!e) return
  const words = text ?? editor.value?.take() ?? e.text
  editing.value = null
  area.value?.focus({ preventScroll: true })
  const current = state.objects[e.id]
  // Words that are one fenced block (```latex … ```) of a type the server makes become a container (D560)
  if (current && current.kind === 'text' && (await session.fenceToContainer(e.id, words))) return
  if (current && words !== wordsOf(current)) await session.writeWords(e.id, words)
}

/** Where a reference goes (step H): at the caret of the words being edited (they are taken first), else at the end
 * of the selected object's words; with the point on the window to open the picker at. `null` for no words. */
async function referencePlace(): Promise<{ id: string; offset: number; x: number; y: number } | null> {
  const id = editing.value?.id ?? state.selected
  const o = id ? state.objects[id] : null
  if (!id || !o?.paragraph || o.paragraph.generated) return null
  const rect = document.querySelector<HTMLElement>(`.obj[data-id="${CSS.escape(id)}"]`)?.getBoundingClientRect()
  const offset = editing.value ? (editor.value?.caretOffset() ?? 0) : o.paragraph.text.length
  if (editing.value) await commitEdit()
  return { id, offset, x: rect ? rect.left : 200, y: rect ? rect.bottom + 6 : 200 }
}

function cancelEdit() {
  if (!editing.value) return
  editing.value = null
  area.value?.focus({ preventScroll: true })
}

// ------------------------------------------------------------------------------ keys

// Writing into a text box is a person going on from where a tag took them (D1312); a click on the slide is the same.
watch(
  () => editing.value || containerEditing.value,
  (now) => {
    if (now) session.clearBack()
  },
)
async function onKey(event: KeyboardEvent) {
  const o = selected.value
  if (editing.value || containerEditing.value) return
  if ((event.target as HTMLElement).closest('[role=dialog]')) return // a popover on the slide (Rotate by…) has its own keys: Enter submits, Backspace edits the number
  if (event.key === 'Escape') {
    if (cancelTurn()) return
    return void session.select(null)
  }
  if (!o) return
  if (event.key === 'Enter' || event.key === 'F2') {
    event.preventDefault()
    return void beginEdit()
  }
  if (readonly.value) return
  if (event.key === 'Delete' || event.key === 'Backspace') {
    event.preventDefault()
    return void session.remove(o.id)
  }
  const arrows: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }
  const arrow = arrows[event.key]
  if (arrow) {
    event.preventDefault()
    const step = event.shiftKey ? NUDGE_FINE : NUDGE
    const f = o.rotation ? moveTurned(slideFrame(o), o.rotation, arrow[0] * step, arrow[1] * step, null) : moveFrame(slideFrame(o), arrow[0] * step, arrow[1] * step)
    if (f.x !== o.anchor.x || f.y !== o.anchor.y) await session.move(o.id, f.x, f.y)
  }
}

defineExpose({ paste: () => clip.paste(), focus: () => area.value?.focus(), beginEdit, openStyleMenu, openDescribe, quarter, openRotateBy, referencePlace })

</script>

<template>
  <div
    ref="area"
    class="area"
    tabindex="0"
    :aria-label="t('slide')"
    @pointerdown.capture="session.clearBack()"
    @keydown="onKey"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
  >
    <div
      ref="slideEl"
      class="slide"
      :class="{ grid: props.showGrid }"
      data-testid="slide"
      :data-slide="state.activeSlide"
      :style="{ width: px(SLIDE_W), height: px(SLIDE_H), ...gridStyle }"
      @pointerdown="onSlideDown"
    >
      <div
        v-for="o in objects"
        :key="o.id"
        class="obj"
        :class="[o.kind, { selected: o.id === state.selected, empty: wordsOf(o) === '' && !o.paragraph?.generated }, replayClass(o.id)]"
        :style="boxStyle(o)"
        :data-id="o.id"
        :data-thing="o.id"
        :aria-label="label(o)"
        role="button"
        @pointerdown="onObjectDown($event, o)"
        @dblclick.stop="beginEdit(o.id)"
        @contextmenu="onObjectContext($event, o)"
      >
        <img v-if="o.kind === 'image'" class="picture" :src="pictureSrc(o)" alt="" draggable="false" >
        <template v-else-if="o.kind === 'rendered'">
          <RenderedEditor
            v-if="containerEditing === o.id && faceOf(o)"
            :text="faceOf(o)!.definition.source"
            :label="faceOf(o)!.label"
            @commit="commitContainer(o, $event)"
            @cancel="cancelContainer"
          />
          <RenderedFace v-else-if="faceOf(o)" :src="faceOf(o)!.src" :status="faceOf(o)!.status" :label="faceOf(o)!.label" />
        </template>
        <template v-else>
          <svg v-if="outline(o)" class="shape" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <path :d="outline(o)!.path" vector-effect="non-scaling-stroke" :style="paintCss(o)" />
          </svg>
          <div class="words" :style="textStyle(o)">
            <span v-if="wordsOf(o) === '' && o.kind === 'text' && !o.paragraph?.generated && editing?.id !== o.id" class="hint">{{ t('Double-click to type') }}</span>
            <ParagraphWords v-else-if="editing?.id !== o.id" :text="wordsOf(o)" :marks="marksOf(o.id)" :marker="session.markOf(o.id)?.marker" :indent="session.markOf(o.id)?.indent" :entries="session.agendaOf(o.id)" :leader="o.paragraph?.generated?.leader" :shown="state.referenced[o.id] ?? null" />
          </div>
          <ParagraphEditor
            v-if="editing?.id === o.id"
            :ref="setEditor"
            class="editor"
            :text="editing.text"
            :label="t('text of the object')"
            :marker="session.markOf(o.id)?.marker"
            :indent="session.markOf(o.id)?.indent"
            :shown="state.referenced[o.id] ?? null"
            :style="editorStyle(o)"
            @commit="commitEdit"
            @cancel="cancelEdit"
          />
        </template>
      </div>

      <!-- what colleagues have selected: their colour and name -->
      <template v-for="other in others" :key="`${other.user}:${other.id}`">
        <div
          v-if="state.objects[other.id]"
          class="other"
          :style="{ ...boxStyle(state.objects[other.id]!), borderColor: colorOf(state, other.user) }"
          :title="other.locked ? t('{user} is working on this', { user: other.user }) : t('{user} selected this', { user: other.user })"
        >
          <span class="tag" :style="{ background: colorOf(state, other.user), color: inkOn(colorOf(state, other.user)) }">{{ other.user }}</span>
        </div>
      </template>

      <!-- my selection and its handles -->
      <div v-if="selected && selectedFrame" class="mine" :style="{ left: px(selectedFrame.x), top: px(selectedFrame.y), width: px(selectedFrame.w), height: px(selectedFrame.h), ...turnCss(selectedTurn) }">
        <ObjectFrame :handles="handles" :turnable="turnable" :turn="selectedTurn" :turning="interaction.turningNow(selected.id)" :below="handleBelow" @handle="onHandleDown" @turn-down="onTurnDown" @turn-key="onTurnKey" />
      </div>
    </div>

    <p class="sr" role="status" aria-live="polite">{{ turnSaid }}</p>
    <RotatePopover v-if="rotating && rotatePreview" :x="rotating.x" :y="rotating.y" :rotation="rotatePreview.from" @preview="previewTurn" @done="doneRotateBy" @cancel="cancelRotateBy" />
    <ContextMenu v-if="contextMenu" :x="contextMenu.x" :y="contextMenu.y" :items="contextItems" :label="t('Object menu')" @close="closeContextMenu" />
    <StyleMenu v-if="styleMenu" :host="styleHost" :x="styleMenu.x" :y="styleMenu.y" :mode="styleMenu.mode" :properties="pictureProperties" @close="styleMenu = null" @styles="((styleMenu = null), emit('styles'))" />
    <NameAndDescribeDialog v-if="nameDialog.details.value" :details="nameDialog.details.value" @save="nameDialog.save" @close="nameDialog.close" />
    <ImagePropertiesDialog v-if="propertiesObject" :session="session" :object="propertiesObject" @close="propertiesFor = null" />
  </div>
</template>

<style scoped>
.area {
  display: grid;
  place-items: center;
  overflow: hidden;
  background: color-mix(in srgb, var(--ink) 6%, var(--paper));
  outline: none;
  min-width: 0;
  min-height: 0;
  touch-action: none;
}
.slide {
  position: relative;
  background: #fff;
  box-shadow: var(--shadow);
  overflow: hidden;
  user-select: none;
}
.slide.grid {
  /* E10.15: a helper the view draws, never part of the slide itself — background-position/-size only, so it
   * never shows up in anything that exports or prints the slide's own content. */
  background-image: linear-gradient(to right, var(--grid) 1px, transparent 1px), linear-gradient(to bottom, var(--grid) 1px, transparent 1px);
  background-position: -1px -1px;
}
.obj {
  position: absolute;
  cursor: default;
}
.obj.selected {
  cursor: move;
}
.obj.text.empty:not(.selected) {
  outline: 1px dashed var(--line);
}
.obj.text:hover {
  outline: 1px dashed var(--line);
}
.shape {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
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
.words {
  position: absolute;
  overflow: hidden;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  pointer-events: none;
}
.hint {
  color: var(--muted);
  font-style: italic;
  font-size: 0.7em;
}
.editor {
  position: absolute;
  border: none;
  outline: 2px solid var(--iris);
  background: rgb(255 255 255 / 85%);
  margin: 0;
  padding: 0;
  overflow: hidden;
  pointer-events: auto;
}
.mine {
  position: absolute;
  outline: 2px solid var(--iris);
  pointer-events: none;
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
.other {
  position: absolute;
  border: 2px solid;
  pointer-events: none;
}
.tag {
  position: absolute;
  top: -20px;
  left: -2px;
  font-size: 11px;
  font-weight: 500;
  padding: 1px 7px;
  border-radius: 999px;
  white-space: nowrap;
}
</style>
