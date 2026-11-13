<script setup lang="ts">
// File ▸ Download (D141, E2.9; moved here from File ▸ Manage ▸ Export… by D212, which put the new format picker
// in its place). Claudia's own file format only: a JSON snapshot of the document's current content, sealed with
// nothing (it is already decrypted content you are allowed to see) and saved straight to this computer. Word,
// Excel and PowerPoint export is `ExportFormatDialog.vue`, under File ▸ Export…; neither dialog includes the
// command history or the chat — both stay in the document, only not in either file.
import { ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { downloadJSON } from '~/lib/download'

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: [] }>()

const busy = ref(false)
const done = ref(false)

async function exportNow() {
  busy.value = true
  const data = await props.session.exportContent()
  if (data !== false) {
    downloadJSON(`${props.session.state.doc}.claudia-export.json`, data)
    done.value = true
  }
  busy.value = false
}
</script>

<template>
  <Modal title="Export this document" @close="emit('close')">
    <p class="lead">
      This saves <b>{{ session.state.doc }}</b>'s current content to this computer as Claudia's own file format (a JSON snapshot) — not a Word, Excel or
      PowerPoint file; for one of those, use File ▸ Export… instead. It does not include the document's history or chat.
    </p>
    <p v-if="done" class="lead">Exported.</p>
    <div class="buttons">
      <button v-if="!done" class="btn primary" type="button" :disabled="busy" @click="exportNow">Export</button>
      <button class="btn" type="button" @click="emit('close')">{{ done ? 'Done' : 'Cancel' }}</button>
    </div>
  </Modal>
</template>

<style scoped>
.lead {
  margin: 0;
  color: var(--muted);
}
.buttons {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
</style>
