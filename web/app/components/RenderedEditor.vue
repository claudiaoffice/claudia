<script setup lang="ts">
// The text of a rendered container, while it is being written: Ctrl+Enter or a click outside draws it, Esc leaves it as
// it was, Enter is a new line (formulas and diagrams have many). Labelled for a screen reader with the type's name.
import { onMounted, ref } from 'vue'
import { useI18n } from '~/lib/i18n'

const props = defineProps<{ text: string; label: string }>()
const emit = defineEmits<{ commit: [text: string]; cancel: [] }>()
const { t } = useI18n()
const value = ref(props.text)
const box = ref<HTMLTextAreaElement | null>(null)
let done = false

onMounted(() => {
  box.value?.focus()
  box.value?.setSelectionRange(value.value.length, value.value.length)
})

function finish(commit: boolean) {
  if (done) return
  done = true
  if (commit) emit('commit', value.value)
  else emit('cancel')
}

function onKey(event: KeyboardEvent) {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    finish(true)
  } else if (event.key === 'Escape') {
    event.preventDefault()
    finish(false)
  }
  event.stopPropagation()
}
</script>

<template>
  <div class="editor" data-testid="rendered-editor" @pointerdown.stop @dblclick.stop>
    <span class="type">{{ props.label }}</span>
    <textarea
      ref="box"
      v-model="value"
      spellcheck="false"
      :aria-label="t('Text of the {type} container', { type: props.label })"
      :aria-description="t('Ctrl+Enter draws it, Escape leaves it as it was')"
      @keydown="onKey"
      @blur="finish(true)"
    />
  </div>
</template>

<style scoped>
.editor {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  background: var(--paper);
  outline: 2px solid var(--iris);
}
.type {
  font-size: 10px;
  padding: 0 6px;
  color: var(--muted);
  border-bottom: 1px solid var(--line);
}
textarea {
  flex: 1;
  min-height: 0;
  resize: none;
  border: none;
  outline: none;
  margin: 0;
  padding: 6px;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  background: transparent;
  color: var(--ink);
}
</style>
