<script setup lang="ts">
// File ▸ Download (D141, E2.9; moved here from File ▸ Manage ▸ Export… by D212, which put the new format picker
// in its place). Claudia's own file format only: a JSON snapshot of the document's current content, sealed with
// nothing (it is already decrypted content you are allowed to see) and saved straight to this computer. Word,
// Excel and PowerPoint export is `ExportFormatDialog.vue`, under File ▸ Export…; neither dialog includes the
// command history or the chat — both stay in the document, only not in either file.
import { ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { downloadJSON } from '~/lib/download'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: [] }>()

const busy = ref(false)
const done = ref(false)
/** Where a desktop window saved it (D501): the person chose it, and sees it again here. */
const savedTo = ref('')
const problem = ref('')

async function exportNow() {
  busy.value = true
  problem.value = ''
  try {
    const data = await props.session.exportContent()
    if (data !== false) {
      const saved = await downloadJSON(`${props.session.state.doc}.claudia-export.json`, data)
      if (saved.kind !== 'cancelled') {
        savedTo.value = saved.kind === 'downloaded' ? '' : saved.path
        done.value = true
      }
    }
  } catch (e) {
    problem.value = t('The file could not be saved: {reason}', { reason: (e as Error).message })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Modal :title="t('Export this document')" @close="emit('close')">
    <TransText tag="p" class="lead" :text="t('This saves the current content of {doc} to this computer as Claudia\'s own file format (a JSON snapshot) — not a Word, Excel or PowerPoint file; for one of those, use File ▸ Export… instead. It does not include the document\'s history or chat.')">
      <template #doc><b>{{ session.state.doc }}</b></template>
    </TransText>
    <p v-if="done && savedTo" class="lead" data-testid="export-saved-to">{{ t('Saved as {path}.', { path: savedTo }) }}</p>
    <p v-else-if="done" class="lead">{{ t('Exported.') }}</p>
    <p v-if="problem" class="error" role="alert">{{ problem }}</p>
    <div class="buttons">
      <button v-if="!done" class="btn primary" type="button" :disabled="busy" @click="exportNow">{{ t('Export') }}</button>
      <button class="btn" type="button" @click="emit('close')">{{ done ? t('Done') : t('Cancel') }}</button>
    </div>
  </Modal>
</template>

<style scoped>
.lead {
  margin: 0;
  color: var(--muted);
}
.error {
  margin: 0;
  color: var(--rose);
}
.buttons {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
</style>
