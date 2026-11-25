<script setup lang="ts">
// File ▸ Export… (D212). Picks a target file format and saves the document's current content to this computer in
// it — Word, Excel, PowerPoint or OpenDocument, or (composes only) plain Markdown — without tracked changes, history or chat.
// Claudia's own sealed file is File ▸ Download (`DownloadDialog.vue`, D110); this is the home of "Export…". The last
// format is Claudia's own unencrypted zip (D1270): it asks once, in words, before it is saved, because the file is not
// protected, and the server records it in the document (D1271). Only owners may add the history and the chat to it.
import { computed, onMounted, ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { downloadBase64, downloadText, type Saved } from '~/lib/download'
import { UNPROTECTED } from '~/lib/audit'
import { lossLines, type LossLine } from '~/lib/export-losses'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

/** One target format this app offers. `local`, when given, builds the file here, with no server round trip (the
 * only case today is composes' Markdown, which is already in the browser as `state.paragraphs`); its absence means
 * the dialog asks the server instead, via `exportOffice`. `value` doubles as the file's extension. */
export interface ExportFormatOption {
  value: string
  label: string
  mimeType?: string // required together with `local`
  local?: () => string
}

const props = defineProps<{ session: BaseSession; formats: ExportFormatOption[] }>()
const emit = defineEmits<{ close: [] }>()

/** Every app's formats, and then Claudia's own unencrypted zip, which every app offers the same way (D1270). */
const all = computed<ExportFormatOption[]>(() => [...props.formats, { value: UNPROTECTED, label: t('Claudia, unencrypted (JSON in a zip)') }])
const chosen = ref(props.formats[0]?.value ?? UNPROTECTED)
const unprotected = computed(() => chosen.value === UNPROTECTED)
const owner = computed(() => props.session.state.me.role === 'owner')
/** Owners only (D1270); off unless asked for. */
const withHistory = ref(false)
/** The question "Save without protection?", asked once before the unencrypted file is made. */
const confirming = ref(false)
const busy = ref(false)
const done = ref(false)
/** Where a desktop window saved it (D501): the person chose it, and sees it again here. */
const savedTo = ref('')
const problem = ref('')
/** What the file could not hold, a line per kind (UX-70, D405); `null` for a format that does not say. */
const losses = ref<LossLine[] | null>(null)

// A4: a paragraph's description can go into the file as a review comment, by whoever exports it, dated today. The tick
// is off by default and is there only when there is a description to write and the format can carry a comment.
const descriptions = ref(0)
const comments = ref(false)
const offerComments = computed(() => descriptions.value > 0 && ['docx', 'odt'].includes(chosen.value) && !props.formats.find((f) => f.value === chosen.value)?.local)
onMounted(async () => {
  descriptions.value = await props.session.exportDescriptions()
})

/** The file is out: downloaded in a browser tab, saved where the person chose in a desktop window. A cancelled Save
 * dialog leaves this dialog as it was, to try again or close. */
function finished(saved: Saved) {
  if (saved.kind === 'cancelled') return
  savedTo.value = saved.kind === 'downloaded' ? '' : saved.path
  done.value = true
}

function start() {
  if (unprotected.value) confirming.value = true
  else void exportNow()
}

async function exportNow() {
  confirming.value = false
  busy.value = true
  problem.value = ''
  try {
    if (unprotected.value) {
      const result = await props.session.exportClaudia(owner.value && withHistory.value)
      if (result !== false) finished(await downloadBase64(result.filename, result.content_type, result.data))
      return
    }
    const format = props.formats.find((f) => f.value === chosen.value)
    if (!format) return
    if (format.local) {
      finished(await downloadText(`${props.session.state.doc}.${format.value}`, format.local(), format.mimeType))
    } else {
      const result = await props.session.exportOffice(format.value, { descriptionComments: offerComments.value && comments.value })
      if (result === false) return
      finished(await downloadBase64(`${props.session.state.doc}.${format.value}`, result.content_type, result.data))
      losses.value = result.losses ? lossLines(result.losses, t) : null
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
    <TransText v-if="unprotected" tag="p" class="lead" :text="t('This saves {doc} to this computer in Claudia\'s own format, as plain files in a zip that anyone can open.')">
      <template #doc><b>{{ session.state.doc }}</b></template>
    </TransText>
    <TransText v-else tag="p" class="lead" :text="t('This saves the current content of {doc} to this computer, in the format you pick below. It does not include the document\'s history or chat, and no tracked changes are kept — just the content as it stands now.')">
      <template #doc><b>{{ session.state.doc }}</b></template>
    </TransText>
    <label v-if="!done && !confirming" class="field">
      {{ t('Save as') }}<select v-model="chosen" data-testid="export-format">
        <option v-for="f in all" :key="f.value" :value="f.value">{{ f.label }}</option>
      </select>
    </label>
    <label v-if="!done && offerComments" class="check" data-testid="export-description-comments">
      <input v-model="comments" type="checkbox">
      {{ t('Write paragraph descriptions as comments') }}
    </label>
    <template v-if="!done && !confirming && unprotected">
      <label v-if="owner" class="check">
        <input v-model="withHistory" type="checkbox" data-testid="export-history" aria-describedby="export-history-hint">
        {{ t('Include history and chat') }}
      </label>
      <p v-if="owner" id="export-history-hint" class="hint">{{ t('Owners only. Hidden lines are included. Without it the file holds the content as it is now.') }}</p>
      <p v-else class="hint" data-testid="export-owners-only">{{ t('The file holds the content as it is now. History and chat can only be exported by owners.') }}</p>
    </template>
    <div v-if="confirming" class="confirm" role="alertdialog" aria-labelledby="unprotected-title" aria-describedby="unprotected-text" data-testid="export-unprotected-confirm">
      <h3 id="unprotected-title">{{ t('Save without protection?') }}</h3>
      <div id="unprotected-text">
        <p>{{ t('The file will not be protected by a password.') }}</p>
        <p>{{ t('Anyone who gets the file can read it.') }}</p>
        <p>{{ t('The export is recorded in the document: who, when and what.') }}</p>
        <p>{{ t('Claudia cannot tell whether someone copies from the screen.') }}</p>
      </div>
    </div>
    <!-- always on the page, so that a screen reader says what comes into it (BITV 4.1.3) -->
    <div role="status" data-testid="export-result">
      <template v-if="done">
        <p v-if="savedTo" class="lead" data-testid="export-saved-to">{{ t('Saved as {path}.', { path: savedTo }) }}</p>
        <p v-else class="lead">{{ t('Exported.') }}</p>
        <template v-if="losses?.length">
          <p class="lost-head">{{ t('The file does not hold:') }}</p>
          <ul class="lost" data-testid="export-losses">
            <li v-for="line in losses" :key="line.kind" :data-loss="line.kind">
              <span class="what">{{ line.title }}</span>
              <span class="why">{{ line.hint }}</span>
            </li>
          </ul>
          <p class="hint">{{ t('Everything else is in the file.') }}</p>
        </template>
        <p v-else-if="losses" class="hint" data-testid="export-nothing-lost">{{ t('Everything is in the file.') }}</p>
      </template>
    </div>
    <p v-if="problem" class="error" role="alert">{{ problem }}</p>
    <div class="buttons">
      <button v-if="!done && !confirming" class="btn primary" type="button" :disabled="busy" @click="start">{{ t('Export') }}</button>
      <button v-if="confirming" class="btn primary" type="button" :disabled="busy" data-testid="export-unprotected" @click="exportNow">{{ t('Export unprotected') }}</button>
      <button v-if="confirming" class="btn" type="button" @click="confirming = false">{{ t('Cancel') }}</button>
      <button v-else class="btn" type="button" @click="emit('close')">{{ done ? t('Done') : t('Cancel') }}</button>
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
.hint {
  margin: 0;
  color: var(--muted);
  font-size: 12.5px;
}
.check {
  display: flex;
  align-items: center;
  gap: 8px;
}
.confirm {
  border: 1px solid var(--rose);
  border-radius: 10px;
  padding: 8px 14px;
}
.confirm h3 {
  margin: 0 0 6px;
  font-size: 14px;
}
.confirm p {
  margin: 4px 0;
}
.field {
  display: flex;
  align-items: center;
  gap: 8px;
}
.check {
  display: flex;
  align-items: center;
  gap: 8px;
}
.buttons {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
.lost-head {
  margin: 8px 0 0;
  font-weight: 600;
}
.lost {
  margin: 6px 0;
  padding-left: 18px;
}
.lost li {
  margin: 0 0 6px;
}
.lost li::marker {
  color: var(--apricot-dark);
}
.what {
  display: block;
}
.why {
  display: block;
  color: var(--muted);
  font-size: 12.5px;
}
</style>
