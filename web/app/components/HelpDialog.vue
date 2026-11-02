<script setup lang="ts">
const props = withDefaults(defineProps<{ app?: string }>(), { app: 'computes' })
const emit = defineEmits<{ close: [] }>()
const tableKeys: [string, string][] = [
  ['Arrows, Tab, Enter', 'move through the table'],
  ['Shift + arrows or drag', 'select a block'],
  ['Ctrl + arrows', 'jump to the edge of a block of data'],
  ['Type, F2 or double click', 'edit a cell (others are kept out of it while you do)'],
  ['Enter / Tab / Esc', 'keep and go down / keep and go right / cancel'],
  ['Delete', 'clear the selected cells'],
  ['Ctrl + C / V', 'copy and paste, also from and to other programs'],
  ['Ctrl + Z / Y', 'undo / redo your own changes'],
  ['Ctrl + S', 'save a checkpoint'],
]
const textKeys: [string, string][] = [
  ['Type', 'write; a word is sent when it ends, and the others see where you are'],
  ['Enter', 'end the paragraph (after a heading the next one is body text)'],
  ['Backspace / Delete', 'delete; at the edge of a paragraph it joins the one next to it'],
  ['Ctrl + Backspace / Delete', 'delete a word'],
  ['Ctrl + C / X / V', 'copy, cut and paste (as plain text)'],
  ['Ctrl + Z / Y', 'undo / redo your own changes'],
  ['Ctrl + S', 'save a checkpoint'],
  ['@ai review this text', 'the assistant suggests changes; you accept or reject each'],
]
const keys = props.app === 'composes' ? textKeys : tableKeys
</script>

<template>
  <Modal title="Keyboard" @close="emit('close')">
    <dl>
      <template v-for="[k, v] in keys" :key="k">
        <dt class="mono">{{ k }}</dt>
        <dd>{{ v }}</dd>
      </template>
    </dl>
    <button class="btn primary" type="button" @click="emit('close')">Close</button>
  </Modal>
</template>

<style scoped>
dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 18px;
  margin: 0;
}
dt {
  font-size: 12px;
  color: var(--app-dark);
  white-space: nowrap;
}
dd {
  margin: 0;
}
button {
  justify-self: start;
}
</style>
