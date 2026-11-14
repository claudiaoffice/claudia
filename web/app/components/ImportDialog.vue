<script setup lang="ts">
// After a file has been chosen (sheet 10, C; D438-D442). An Office or OpenDocument file becomes a new document of its
// app here, and the file goes into it unless the person unticks the box; a Claudia file goes in as it is and is then
// opened with a name and password it already knows. The file has already been handed to this place's server
// (`POST /api/uploads`): a page only ever talks to its own server (D170), so "here" is the place it goes to.
import { ref } from 'vue'
import type { Uploaded } from '~/lib/open'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  file: Uploaded
  /** The place the file goes to: this page's server, in the words of the sidebar. */
  place: string
  user: string
  busy: boolean
  error: string
}>()
const emit = defineEmits<{
  close: []
  /** Make the new document: its id, the owner's name and password, and whether the file is kept inside. */
  import: [values: { id: string; user: string; password: string; keep: boolean }]
  /** Put the Claudia file into this place as it is. */
  place: []
  /** Open the document of that id that is here already. */
  existing: []
}>()

const id = ref(props.file.suggested_id ?? '')
const user = ref(props.user)
const password = ref('')
const keep = ref(true)
const claudia = props.file.format === 'claudia'
const appName: Record<string, string> = { computes: t('a table'), composes: t('a text'), creates: t('slides') }
const formatName: Record<string, string> = {
  docx: 'Word',
  xlsx: 'Excel',
  pptx: 'PowerPoint',
  odt: 'OpenDocument',
  ods: 'OpenDocument',
  odp: 'OpenDocument',
}

function size(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} kB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function submit() {
  if (claudia) emit('place')
  else emit('import', { id: id.value.trim(), user: user.value.trim(), password: password.value, keep: keep.value })
}
</script>

<template>
  <Modal :title="t('Open {name}', { name: file.name })" :width="560" @close="emit('close')">
    <div class="file">
      <AppIcon :size="34" :app="file.app" />
      <div>
        <div class="name">{{ file.name }}</div>
        <div class="meta">{{ claudia ? t('Sealed Claudia document') : file.kind }} · {{ size(file.size) }}</div>
      </div>
    </div>
    <form class="form" @submit.prevent="submit">
      <template v-if="!claudia">
        <p class="lead">
          {{ t('Claudia makes {what} of it, and the file goes into the new document with it, sealed. The file on this computer stays as it is.', { what: appName[file.app] ?? file.app }) }}
        </p>
        <p class="where">{{ t('Put it in') }}: <b>{{ place }}</b></p>
        <label class="field">{{ t('Name') }}<input v-model="id" name="import-name" autocomplete="off" required ></label>
        <div class="two">
          <label class="field">{{ t('Your name') }}<input v-model="user" name="import-user" autocomplete="username" required ></label>
          <label class="field">{{ t('Password') }}<input v-model="password" name="import-password" type="password" autocomplete="new-password" required ></label>
        </div>
        <label class="check">
          <input v-model="keep" type="checkbox" name="keep-original" >
          <span>{{ t('Keep the {format} file inside the document: Download then gives back this file with only your changes.', { format: formatName[file.format] ?? file.format }) }}</span>
        </label>
        <p class="hint">{{ t('You are its owner. What the document does not show stays in the kept file and is listed after it opens.') }}</p>
      </template>
      <template v-else>
        <p class="lead">{{ t('A Claudia document goes into a place as it is, still sealed, and is opened with a name and password it already knows.') }}</p>
        <p class="where">{{ t('Put it in') }}: <b>{{ place }}</b></p>
        <p v-if="file.exists" class="warn" role="status">
          {{ t('{place} already holds a document called {id}. A name cannot change (it is sealed into the file): open the one that is here, or open the place you want it in first.', { place, id: file.id ?? '' }) }}
        </p>
      </template>
      <p v-if="!file.hosted" class="error" role="alert">{{ t('This place does not keep documents of this kind.') }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="buttons">
        <button class="btn" type="button" :disabled="busy" @click="emit('close')">{{ t('Cancel') }}</button>
        <button v-if="claudia && file.exists" class="btn primary" type="button" :disabled="busy" @click="emit('existing')">{{ t('Open the one here') }}</button>
        <button v-else class="btn primary" type="submit" :disabled="busy || !file.hosted">{{ claudia ? t('Put it in') : t('Open') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.file {
  display: flex;
  gap: 12px;
  align-items: center;
}
.name {
  font-weight: 600;
}
.meta,
.hint {
  color: var(--muted);
  font-size: 12px;
  margin: 0;
}
.form {
  display: grid;
  gap: 12px;
}
.lead,
.where {
  margin: 0;
}
.two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.check {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.check input {
  margin-top: 3px;
}
.warn {
  margin: 0;
  padding: 10px 12px;
  border-radius: 9px;
  background: var(--app-soft);
}
.error {
  color: var(--rose);
  margin: 0;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
