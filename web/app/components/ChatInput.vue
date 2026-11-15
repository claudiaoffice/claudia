<script setup lang="ts">
// The chat box (E5.20, D551). It holds words and chips: a tag is a chip you cannot enter, delete as a whole and that shows
// the thing's name as it is now. The message it gives is still the text `[#name](thing:id)`, so everything else (the
// history, the AI, exports) reads it as before. One line: Enter sends. The rules for the message and the places in it are
// in `lib/chip-text.ts`; this file only does the DOM.
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { MAX_MESSAGE, messageOf, offsetOf, placeOf, type Piece, type Place } from '~/lib/chip-text'
import { splitTags } from '~/lib/tags'

defineOptions({ inheritAttrs: false })
const props = defineProps<{
  modelValue: string
  /** The name a thing has now, or `undefined` for one the document does not know. */
  nameOf: (id: string) => string | undefined
  /** Is the thing known to be gone? A chip to it is struck through. */
  isGone: (id: string) => boolean
  placeholder: string
}>()
const emit = defineEmits<{
  'update:modelValue': [value: string]
  /** Where the caret is in the message. */
  caret: [offset: number]
  /** Every key, before the box treats it: a handler that takes it calls `preventDefault`. */
  key: [event: KeyboardEvent]
  /** Enter, when nothing else took it. */
  submit: []
  focus: []
  blur: []
}>()

const root = ref<HTMLElement | null>(null)
let current = '' // the message the box holds, as last given or read
const chips = ref<{ id: string; written: string }[]>([])

function chipNode(id: string, written: string): HTMLElement {
  const node = document.createElement('span')
  node.className = 'chip'
  node.contentEditable = 'false'
  node.dataset.chip = id
  node.dataset.written = written
  fill(node)
  return node
}
function fill(node: HTMLElement) {
  const id = node.dataset.chip!
  node.textContent = `#${props.nameOf(id) ?? node.dataset.written ?? ''}`
  node.classList.toggle('gone', props.isGone(id))
}
function render(text: string) {
  const el = root.value
  if (!el) return
  const nodes: Node[] = []
  for (const segment of splitTags(text)) {
    if (segment.type === 'tag') nodes.push(chipNode(segment.id, segment.name))
    else if (segment.text) nodes.push(document.createTextNode(segment.text))
  }
  if (nodes.length && nodes[nodes.length - 1] instanceof HTMLElement) nodes.push(document.createTextNode(''))
  el.replaceChildren(...nodes)
  chips.value = read().flatMap((p) => (p.type === 'tag' ? [{ id: p.id, written: p.name }] : []))
}

function read(): Piece[] {
  const out: Piece[] = []
  for (const node of root.value?.childNodes ?? []) {
    if (node.nodeType === Node.TEXT_NODE) out.push({ type: 'text', text: node.nodeValue ?? '' })
    else if (node instanceof HTMLElement && node.dataset.chip) out.push({ type: 'tag', id: node.dataset.chip, name: node.dataset.written ?? '' })
    else out.push({ type: 'text', text: (node.textContent ?? '').replace(/\s+/g, ' ') }) // (a browser's leftovers: <br>, <div>)
  }
  return out
}

function placeNow(): Place | null {
  const el = root.value
  const selection = window.getSelection()
  const node = selection?.anchorNode
  if (!el || !selection || !node || !el.contains(node)) return null
  if (node === el) return { index: selection.anchorOffset, inner: 0 }
  const kids = Array.from(el.childNodes)
  const index = kids.findIndex((kid) => kid === node || kid.contains(node))
  if (index < 0) return null
  return { index, inner: node.nodeType === Node.TEXT_NODE && kids[index] === node ? selection.anchorOffset : kids[index] instanceof HTMLElement && (kids[index] as HTMLElement).dataset.chip ? 1 : 0 }
}
function caretNow(): number | null {
  const place = placeNow()
  return place === null ? null : offsetOf(read(), place)
}
/** Put the caret at this position of the message. */
function setCaret(offset: number) {
  const el = root.value
  const selection = window.getSelection()
  if (!el || !selection) return
  const place = placeOf(read(), offset)
  const kid = el.childNodes[place.index]
  const range = document.createRange()
  if (!kid) range.setStart(el, 0)
  else if (kid.nodeType === Node.TEXT_NODE) range.setStart(kid, Math.min(place.inner, (kid as Text).length))
  else if (place.inner === 0) range.setStartBefore(kid)
  else range.setStartAfter(kid)
  range.collapse(true)
  selection.removeAllRanges()
  selection.addRange(range)
}
function focus() {
  root.value?.focus()
}

function onInput() {
  const text = messageOf(read())
  if (text.length > MAX_MESSAGE) {
    // too long: the box goes back to what it held
    render(current)
    setCaret(current.length)
    return
  }
  current = text
  chips.value = read().flatMap((p) => (p.type === 'tag' ? [{ id: p.id, written: p.name }] : []))
  emit('update:modelValue', text)
  noteCaret()
}
function noteCaret() {
  const offset = caretNow()
  if (offset !== null) emit('caret', offset)
}
function onKey(event: KeyboardEvent) {
  emit('key', event)
  if (event.defaultPrevented || event.isComposing) return
  if (event.key === 'Enter') {
    event.preventDefault()
    emit('submit')
  } else if ((event.ctrlKey || event.metaKey) && ['b', 'i', 'u'].includes(event.key.toLowerCase())) event.preventDefault() // (no formatting)
}
function onBeforeInput(event: InputEvent) {
  if (event.inputType.startsWith('format') || event.inputType === 'insertParagraph' || event.inputType === 'insertLineBreak') event.preventDefault()
}
function onPaste(event: ClipboardEvent) {
  event.preventDefault()
  const words = (event.clipboardData?.getData('text/plain') ?? '').replace(/\s*[\r\n]+\s*/g, ' ')
  if (words && !document.execCommand('insertText', false, words)) {
    const range = window.getSelection()?.getRangeAt(0)
    if (range) {
      range.deleteContents()
      range.insertNode(document.createTextNode(words))
      range.collapse(false)
    }
    onInput()
  }
}

watch(
  () => props.modelValue,
  (value) => {
    if (value === current) return
    const had = document.activeElement === root.value
    current = value
    render(value)
    if (had) void nextTick(() => setCaret(value.length))
  },
)
// a chip says the name the thing has now, and is struck through once the thing is gone
watch(
  () => chips.value.map((c) => `${props.nameOf(c.id) ?? c.written}|${props.isGone(c.id)}`),
  () => root.value?.querySelectorAll<HTMLElement>('[data-chip]').forEach(fill),
  { flush: 'post' },
)
const selectionChanged = () => {
  if (document.activeElement === root.value) noteCaret()
}
onMounted(() => {
  current = props.modelValue
  render(current)
  document.addEventListener('selectionchange', selectionChanged)
})
onBeforeUnmount(() => document.removeEventListener('selectionchange', selectionChanged))

defineExpose({ focus, setCaret, root })
</script>

<template>
  <div
    ref="root"
    v-bind="$attrs"
    class="chat-input"
    contenteditable="true"
    role="combobox"
    aria-multiline="false"
    spellcheck="true"
    :data-placeholder="placeholder"
    @input="onInput"
    @keydown="onKey"
    @beforeinput="onBeforeInput"
    @paste="onPaste"
    @drop.prevent
    @focus="emit('focus')"
    @blur="emit('blur')"
  />
</template>

<style scoped>
.chat-input {
  flex: 1;
  min-width: 0;
  min-height: 34px;
  box-sizing: border-box;
  border-radius: 999px;
  border: 1px solid rgb(231 225 244 / 22%);
  background: rgb(255 255 255 / 6%);
  padding: 7px 14px;
  color: #fff;
  overflow: hidden;
  white-space: pre; /* (one line, and a space is a space: the browser does not eat the one before the caret) */
  line-height: 20px;
}
.chat-input:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 1px;
}
.chat-input:empty::before {
  content: attr(data-placeholder);
  color: rgb(230 224 245 / 45%);
  pointer-events: none;
}
.chat-input :deep(.chip) {
  display: inline-block;
  margin: 0 1px;
  padding: 0 6px;
  border: 1px solid rgb(231 225 244 / 40%);
  border-radius: 999px;
  background: rgb(255 255 255 / 10%);
  user-select: all;
}
/* a thing that is gone: struck through and dashed, so that colour is not the only sign */
.chat-input :deep(.chip.gone) {
  text-decoration: line-through;
  border-style: dashed;
}
</style>
