<script setup lang="ts">
// File ▸ Export… (D212). Picks a target file format and saves the document's current content to this computer in
// it — Word, Excel, PowerPoint or OpenDocument, or (composes only) plain Markdown — without tracked changes, history or chat.
// Claudia's own sealed file is File ▸ Download (`DownloadDialog.vue`, D110); this is the home of "Export…".
import { ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { downloadBase64, downloadText, type Saved } from '~/lib/download'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

/** One target format this app offers. `local`, when given, builds the file here, with no server round trip (the
 * only case today is composes' Markdown, which is already in the browser as `state.blocks`); its absence means
 * the dialog asks the server instead, via `exportOffice`. `value` doubles as the file's extension. */
export interface ExportFormatOption {
  value: string
  label: string
  mimeType?: string // required together with `local`
  local?: () => string
}

const props = defineProps<{ session: BaseSession; formats: ExportFormatOption[] }>()
const emit = defineEmits<{ close: [] }>()

const chosen = ref(props.formats[0]?.value ?? '')
const busy = ref(false)
const done = ref(false)
/** Where a desktop window saved it (D501): the person chose it, and sees it again here. */
const savedTo = ref('')
const problem = ref('')

/** The file is out: downloaded in a browser tab, saved where the person chose in a desktop window. A cancelled Save
 * dialog leaves this dialog as it was, to try again or close. */
function finished(saved: Saved) {
  if (saved.kind === 'cancelled') return
  savedTo.value = saved.kind === 'downloaded' ? '' : saved.path
  done.value = true
}

async function exportNow() {
  const format = props.formats.find((f) => f.value === chosen.value)
  if (!format) return
  busy.value = true
  problem.value = ''
  try {
    if (format.local) {
      finished(await downloadText(`${props.session.state.doc}.${format.value}`, format.local(), format.mimeType))
    } else {
      const result = await props.session.exportOffice(format.value)
      if (result !== false) finished(await downloadBase64(`${props.session.state.doc}.${format.value}`, result.content_type, result.data))
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
    <TransText tag="p" class="lead" :text="t('This saves the current content of {doc} to this computer, in the format you pick below. It does not include the document\'s history or chat, and no tracked changes are kept — just the content as it stands now.')">
      <template #doc><b>{{ session.state.doc }}</b></template>
    </TransText>
    <label v-if="!done && formats.length > 1" class="field">
      {{ t('Save as') }}<select v-model="chosen">
        <option v-for="f in formats" :key="f.value" :value="f.value">{{ f.label }}</option>
      </select>
    </label>
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
.field {
  display: flex;
  align-items: center;
  gap: 8px;
}
.buttons {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
</style>
