<script setup lang="ts">
// One paragraph, editable: the words of a text box or a shape on a slide (step G of
// claudiaoffice-log/notes/text-structure-across-apps.md). It replaces creates' <textarea>, which could hold nothing but
// plain characters: this editor is the place the reference atoms of step H go. What it writes is saved as typing
// (`write_words`): only what differs from the words the box has changes, so the words that stay keep their writer.
//
// It draws what `ParagraphWords.vue` draws, so the words do not move when editing starts: a list item's marker before
// them (never part of the words), moved in by its level. Keys: Enter takes the words, Shift+Enter breaks the line,
// Esc leaves without them; leaving the box takes them too. A screen reader hears it as a text field with its label.
import { onMounted, ref } from 'vue'
import { MARKER_GAP_EM } from '@claudia/layout'
import { editedWords } from '~/lib/edited-words'

const props = withDefaults(defineProps<{ text: string; label: string; marker?: string | null; indent?: number }>(), { marker: null, indent: 0 })
const emit = defineEmits<{ commit: [text: string]; cancel: [] }>()

const field = ref<HTMLElement | null>(null)
let done = false

function finish(take: boolean) {
  if (done) return
  done = true
  if (take && field.value) emit('commit', editedWords(field.value))
  else emit('cancel')
}

function onKey(event: KeyboardEvent) {
  event.stopPropagation() // the slide's keys (arrows move the object, Delete removes it) are not the words'
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    finish(true)
  } else if (event.key === 'Enter' && event.shiftKey) {
    event.preventDefault()
    insertAtCaret('\n')
  } else if (event.key === 'Escape') {
    event.preventDefault()
    finish(false)
  }
}

/** Put `text` where the caret is, in place of what is selected, and the caret after it. */
function insertAtCaret(text: string) {
  const selection = document.getSelection()
  if (!selection?.rangeCount || !field.value?.contains(selection.anchorNode)) return
  const range = selection.getRangeAt(0)
  range.deleteContents()
  const node = document.createTextNode(text)
  range.insertNode(node)
  range.setStartAfter(node)
  range.collapse(true)
  selection.removeAllRanges()
  selection.addRange(range)
}

/** Pasted words come in as plain text: a paragraph has one look, its style's. */
function onPaste(event: ClipboardEvent) {
  event.preventDefault()
  insertAtCaret(event.clipboardData?.getData('text/plain') ?? '')
}

/** The words as they are now, taken: the editor is done (for a press elsewhere, which ends the editing itself). */
function take(): string {
  done = true
  return field.value ? editedWords(field.value) : props.text
}

/** Put the caret at the end of the words. */
function focus() {
  const el = field.value
  if (!el) return
  el.focus()
  const selection = document.getSelection()
  selection?.selectAllChildren(el)
  selection?.collapseToEnd()
}

onMounted(() => {
  if (field.value) field.value.textContent = props.text
  focus()
})

defineExpose({ focus, take })
</script>

<template>
  <div class="paragraph-editor" :style="indent ? { paddingLeft: `${indent}em` } : undefined">
    <span v-if="marker" class="marker" aria-hidden="true" :style="{ marginRight: `${MARKER_GAP_EM}em` }">{{ marker }}</span
    ><span
      ref="field"
      class="field"
      contenteditable="plaintext-only"
      role="textbox"
      aria-multiline="true"
      :aria-label="label"
      spellcheck="true"
      data-testid="paragraph-editor"
      @keydown="onKey"
      @paste="onPaste"
      @blur="finish(true)"
      @pointerdown.stop
    />
  </div>
</template>

<style scoped>
.paragraph-editor {
  white-space: pre-wrap;
  overflow-wrap: break-word;
}
.marker {
  user-select: none;
}
.field {
  outline: none;
  white-space: pre-wrap;
  caret-color: currentColor;
}
.field:empty::before {
  content: '\200b'; /* an empty field keeps a line's height, so the caret shows */
}
</style>
