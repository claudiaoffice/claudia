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
  /** The tags this place already uses and how often, to suggest from. */
  counts?: { tag: string; count: number }[]
}>()
const emit = defineEmits<{
  close: []
  /** Make the new document: its id, the owner's name and password, whether the file is kept inside, and the
   * description and tags the person left or wrote (both optional). */
  import: [values: { id: string; user: string; password: string; keep: boolean; description: string; tags: string[] }]
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
// What the file says about itself is the start of the two fields; it arrives with the server's answer, so it fills them
// only while the person has not written anything of their own.
const description = ref(props.file.description ?? '')
const tags = ref([...(props.file.tags ?? [])])
const descriptionTouched = ref(false)
const tagsTouched = ref(false)
watch(
  () => [props.file.description, props.file.tags] as const,
  ([said, words]) => {
    if (!descriptionTouched.value) description.value = said ?? ''
    if (!tagsTouched.value) tags.value = [...(words ?? [])]
  },
)
watch(description, (now) => {
  if (now !== (props.file.description ?? '')) descriptionTouched.value = true
})
watch(tags, (now) => {
  if (now.join('\n') !== (props.file.tags ?? []).join('\n')) tagsTouched.value = true
})
const fromFileDescription = computed(() => !!props.file.description && description.value === props.file.description)
const fromFileTags = computed(() => !!props.file.tags?.length && tags.value.join('\n') === props.file.tags.join('\n'))
const claudia = computed(() => props.file.format === 'claudia')
/** An unencrypted Claudia export (D1272): it is read like an office file, but it holds no original to keep. */
const exported = computed(() => props.file.format === 'claudia-export')
const madeText = computed(() => {
  const { made_by: who, made_at: when } = props.file
  if (!who) return t('A Claudia export.')
  const day = when ? new Date(when) : null
  return day && !Number.isNaN(day.getTime())
    ? t('A Claudia export, made by {who} on {date}.', { who, date: day.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) })
    : t('A Claudia export, made by {who}.', { who })
})
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
  else
    emit('import', {
      id: id.value.trim(),
      user: user.value.trim(),
      password: password.value,
      keep: keep.value && !exported.value,
      description: description.value,
      tags: tags.value,
    })
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
        <p v-if="exported" class="lead" data-testid="export-made">{{ madeText }}</p>
        <p v-else class="lead">
          {{ t('Claudia makes {what} of it, and the file goes into the new document with it, sealed. The file on this computer stays as it is.', { what: appName[file.app] ?? file.app }) }}
        </p>
        <p class="where">{{ t('Put it in') }}: <b>{{ place }}</b></p>
        <label class="field">{{ t('Name') }}<input v-model="id" name="import-name" autocomplete="off" required :readonly="working" ></label>
        <DetailsFields
          v-model:description="description"
          v-model:tags="tags"
          :counts="counts ?? []"
          :place="place"
          :readonly="working"
          :description-from-file="fromFileDescription"
          :tags-from-file="fromFileTags"
          id-prefix="import"
        />
        <div class="two">
          <label class="field">{{ t('Your name') }}<input v-model="user" name="import-user" autocomplete="username" required :readonly="working" ></label>
          <label class="field">{{ t('Password') }}<PasswordInput v-model="password" name="import-password" autocomplete="new-password" required :readonly="working" /></label>
        </div>
        <label v-if="!exported" class="check">
          <input v-model="keep" type="checkbox" name="keep-original" :disabled="working" >
          <span>{{ t('Keep the {format} file inside the document: Download then gives back this file with only your changes.', { format: formatName[file.format] ?? file.format }) }}</span>
        </label>
        <p v-if="exported && file.with_history" class="hint">{{ t('You become the owner of the new document. The people named in its history are not given access; their names stay in the history as former people.') }}</p>
        <p v-else-if="exported" class="hint">{{ t('You become the owner of the new document. Nobody else is given access.') }}</p>
        <p v-else class="hint">{{ t('You are its owner. What the document does not show stays in the kept file and is listed after it opens.') }}</p>
      </template>
      <template v-else>
        <p class="lead">{{ t('A Claudia document goes into a place as it is, still sealed, and is opened with a name and password it already knows.') }}</p>
        <p class="where">{{ t('Put it in') }}: <b>{{ place }}</b></p>
        <div v-if="file.description || file.tags?.length" class="theirs" data-testid="own-details">
          <b>{{ t('Description') }}</b>
          <NotesText v-if="file.description" :notes="file.description" />
          <ul v-if="file.tags?.length" class="own-tags" :aria-label="t('Tags')"><li v-for="tag in file.tags" :key="tag">{{ tag }}</li></ul>
          <p class="hint">{{ t('They come with the file and cannot be changed here — use Details… after it is in.') }}</p>
        </div>
        <div role="status">
          <p v-if="file.same_document" class="warn" data-testid="same-document">
            {{ t('{place} already holds this document, as {id}. It cannot be added a second time: open the one that is here.', { place, id: file.same_document }) }}
          </p>
          <p v-else-if="file.exists" class="warn">
            {{ t('{place} already holds a document called {id}. A name cannot change (it is sealed into the file): open the one that is here, or open the place you want it in first.', { place, id: file.id ?? '' }) }}
          </p>
        </div>
      </template>
      <p v-if="!file.hosted" class="error" role="alert">{{ t('This place does not keep documents of this kind.') }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="buttons">
        <button class="btn" type="button" :disabled="working" @click="emit('close')">{{ t('Cancel') }}</button>
        <button v-if="claudia && (file.exists || file.same_document)" class="btn primary" type="button" :disabled="phase !== 'sent' || busy" @click="emit('existing')">{{ t('Open the one here') }}</button>
        <button v-else class="btn primary" type="submit" :disabled="phase !== 'sent' || busy || !file.hosted">{{ claudia ? t('Put it in') : t('Open') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.theirs {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--app-soft);
  font-size: 13px;
}
.own-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  list-style: none;
  margin: 0;
  padding: 0;
}
.own-tags li {
  border-radius: 999px;
  background: var(--surface);
  padding: 1px 10px;
  font-size: 12.5px;
}
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
