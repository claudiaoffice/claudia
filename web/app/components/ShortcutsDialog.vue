<script setup lang="ts">
// Config ▸ Shortcuts (D122, D126): replaces `HelpDialog.vue`. Shows the shared, structured shortcut map
// (`lib/shortcuts.ts`) this app is actually wired to — not a hand-maintained table that can drift from what Ctrl+Z
// really does — plus `extra`, the handful of things that are real and worth knowing but are not a `keydown` shortcut
// at all (a drag, a double-click, an `@ai` mention) and so have no place in that map.
//
// Read-only for now (D122): a remapping UI is deferred, so this dialog has nothing to edit, only to show.
defineProps<{
  /** Already resolved to display strings ( `chordLabel()` ) by the caller, which is the one place that knows the
   * live, reactive shortcut list (enabled/disabled depends on session state the dialog itself has no access to). */
  shortcuts: { label: string; hint: string }[]
  /** Rows with no keyboard chord: a mouse gesture, a typed convention, anything the table would misrepresent as a
   * key combination. */
  extra?: [string, string][]
}>()
const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <Modal title="Shortcuts" @close="emit('close')">
    <dl>
      <template v-for="s in shortcuts" :key="s.label">
        <dt class="mono">{{ s.hint }}</dt>
        <dd>{{ s.label }}</dd>
      </template>
      <template v-for="[k, v] in extra ?? []" :key="k">
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
  color: var(--app-text); /* --app-dark as literal text fails contrast in dark mode — the owner's 2026-11-06 report */
  white-space: nowrap;
}
dd {
  margin: 0;
}
button {
  justify-self: start;
}
</style>
