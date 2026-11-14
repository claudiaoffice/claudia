<script setup lang="ts">
// After a file has been chosen (sheet 10, C; D438-D442). An Office or OpenDocument file becomes a new document of its
// app here, and the file goes into it unless the person unticks the box; a Claudia file goes in as it is and is then
// opened with a name and password it already knows. The dialog comes as soon as a file is chosen, while the file is
// still on its way to this place's server (`POST /api/uploads`): a page only ever talks to its own server (D170), so
// "here" is the place it goes to. One bar shows sending, reading and opening (sheet 11); Open waits for the file.
import { computed, ref, watch } from 'vue'
import type { Uploaded } from '~/lib/open'
import { importBar, type ImportPhase } from '~/lib/import-progress'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  file: Uploaded
  /** The place the file goes to: this page's server, in the words of the sidebar. */
  place: string
  user: string
  busy: boolean
  error: string
  /** Where the import is: sending the file, waiting for Open, reading it on the server, opening the document. */
  phase: ImportPhase
  /** How much of the file has been sent (0 to 1). */
  sent: number
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
// The name the server suggests (it arrives with the file) replaces the one made from the file's name, unless the
// person has written one of their own meanwhile.
watch(
  () => props.file.suggested_id,
  (suggested, before) => {
    if (suggested && id.value === (before ?? '')) id.value = suggested
  },
)
const bar = computed(() => importBar(props.phase, props.sent))
const working = computed(() => props.phase === 'reading' || props.phase === 'opening')
const STEPS = [t('Sending'), t('Reading'), t('Opening')]
const user = ref(props.user)
const password = ref('')
const keep = ref(true)
const claudia = computed(() => props.file.format === 'claudia')
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
  if (props.phase !== 'sent') return
  if (claudia.value) emit('place')
  else emit('import', { id: id.value.trim(), user: user.value.trim(), password: password.value, keep: keep.value })
}
</script>

<template>
  <Modal :title="t('Open a file')" :width="560" @close="emit('close')">
    <div class="file">
      <AppIcon v-if="file.app" :size="34" :app="file.app" />
      <div class="about">
        <div class="name">{{ file.name }}</div>
        <div class="meta">{{ [claudia ? t('Sealed Claudia document') : file.kind, size(file.size)].filter(Boolean).join(' · ') }}</div>
      </div>
    </div>
    <div class="progress">
      <div
        class="bar"
        role="progressbar"
        :aria-label="t('Opening {name}', { name: file.name })"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-valuenow="bar.value ?? undefined"
        :aria-valuetext="bar.text"
      >
        <span v-for="(part, i) in bar.parts" :key="i" class="part">
          <span v-if="part === 'busy'" class="busy" />
          <span v-else class="fill" :style="{ width: `${part * 100}%` }" />
        </span>
      </div>
      <div class="steps" aria-hidden="true">
        <span v-for="(step, i) in STEPS" :key="step" :class="{ now: i === bar.now }">{{ i === bar.now ? bar.text : step }}</span>
      </div>
      <p class="sr-only" role="status">{{ bar.value === null || phase === 'sent' ? bar.text : '' }}</p>
    </div>
    <form class="form" @submit.prevent="submit">
      <template v-if="!claudia">
        <p class="lead">
          {{ t('Claudia makes {what} of it, and the file goes into the new document with it, sealed. The file on this computer stays as it is.', { what: appName[file.app] ?? file.app }) }}
        </p>
        <p class="where">{{ t('Put it in') }}: <b>{{ place }}</b></p>
        <label class="field">{{ t('Name') }}<input v-model="id" name="import-name" autocomplete="off" required :readonly="working" ></label>
        <div class="two">
          <label class="field">{{ t('Your name') }}<input v-model="user" name="import-user" autocomplete="username" required :readonly="working" ></label>
          <label class="field">{{ t('Password') }}<input v-model="password" name="import-password" type="password" autocomplete="new-password" required :readonly="working" ></label>
        </div>
        <label class="check">
          <input v-model="keep" type="checkbox" name="keep-original" :disabled="working" >
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
        <button class="btn" type="button" :disabled="working" @click="emit('close')">{{ t('Cancel') }}</button>
        <button v-if="claudia && file.exists" class="btn primary" type="button" :disabled="phase !== 'sent' || busy" @click="emit('existing')">{{ t('Open the one here') }}</button>
        <button v-else class="btn primary" type="submit" :disabled="phase !== 'sent' || busy || !file.hosted">{{ claudia ? t('Put it in') : t('Open') }}</button>
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
.about {
  min-width: 0;
}
.name {
  font-weight: 600;
  overflow-wrap: anywhere;
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
  overflow-wrap: anywhere;
}
.form input {
  min-width: 0;
}
.check span {
  min-width: 0;
}
.two {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
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
.progress {
  display: grid;
  gap: 6px;
}
.bar {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 3px;
  height: 8px;
}
.part {
  position: relative;
  overflow: hidden;
  border-radius: 4px;
  background: var(--app-soft);
}
.fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: var(--app);
  transition: width 0.2s linear;
}
.busy {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(-45deg, var(--app) 0 8px, transparent 8px 16px);
  background-size: 22.6px 100%;
  opacity: 0.6;
  animation: crawl 0.8s linear infinite;
}
@keyframes crawl {
  to {
    background-position: 22.6px 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .busy {
    animation: none;
  }
  .fill {
    transition: none;
  }
}
.steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 3px;
  color: var(--muted);
  font-size: 12px;
}
.steps .now {
  color: var(--text);
  font-weight: 600;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
