<script setup lang="ts">
const emit = defineEmits<{ close: [] }>()
const keys: [string, string][] = [
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
