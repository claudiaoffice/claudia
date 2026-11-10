<script setup lang="ts">
// File ▸ Export… (D212). Picks a target file format and saves the document's current content to this computer in
// it — Word, Excel or PowerPoint, or (composes only) plain Markdown — without tracked changes, history or chat.
// Claudia's own file format moved to File ▸ Download (`ExportDialog.vue`); this is the new home of "Export…".
import { ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { downloadBase64, downloadText } from '~/lib/download'

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

async function exportNow() {
  const format = props.formats.find((f) => f.value === chosen.value)
  if (!format) return
  busy.value = true
  if (format.local) {
    downloadText(`${props.session.state.doc}.${format.value}`, format.local(), format.mimeType)
    done.value = true
  } else {
    const result = await props.session.exportOffice(format.value)
    if (result !== false) {
      downloadBase64(`${props.session.state.doc}.${format.value}`, result.content_type, result.data)
      done.value = true
    }
  }
  busy.value = false
}
</script>

<template>
  <Modal title="Export this document" @close="emit('close')">
    <p class="lead">
      This saves <b>{{ session.state.doc }}</b>'s current content to this computer, in the format you pick below. It does not include the
      document's history or chat, and no tracked changes are kept — just the content as it stands now.
    </p>
    <label v-if="!done && formats.length > 1" class="field">
      Save as<select v-model="chosen">
        <option v-for="f in formats" :key="f.value" :value="f.value">{{ f.label }}</option>
      </select>
    </label>
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
