<script setup lang="ts">
// Server settings ▸ Fonts ▸ Add fonts… (E3.13 f, D1041; board `notes/mockups/fonts-2-add-fonts.svg`): check first, then
// add. Step A: the files (TrueType, OpenType, or a .zip of them), the collection's name, who may receive the fonts and
// the licence in words; choosing files already holds them on the server and checks them, which changes nothing but
// fills in the licence the fonts name. Step B: one line per font, what it becomes, and what adding will do, said
// before it happens. Only "Add" changes the server. Files given up are let go of on the server at once (Cancel,
// Start again, closing, a failed upload), and the limits are said before anything is sent (CODE-49).
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { adminApi, AdminApiError } from '~/lib/admin-api'
import {
  checkDescription,
  checkLine,
  scopeSentences,
  suggestedLicence,
  tooMuchToAdd,
  type CheckAnswer,
  type FontLimits,
  type FontsPage,
  type MayGo,
} from '~/lib/admin-fonts'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ token: string; server: string; accessSecretSet: boolean; limits: FontLimits }>()
const emit = defineEmits<{ close: []; added: [page: FontsPage] }>()

const step = ref<'choose' | 'check'>('choose')
const held = ref<{ token: string; name: string; size: number }[]>([])
let added = false
const answer = ref<CheckAnswer | null>(null)
const name = ref('')
const licence = ref('')
const mayGo = ref<MayGo | null>(null)
const busy = ref(false)
const error = ref('')
const dragging = ref(false)
const picker = ref<HTMLInputElement | null>(null)
const nameField = ref<HTMLInputElement | null>(null)

onMounted(() => picker.value?.focus())
// Closing the dialog without adding lets go of what the server holds for it.
onBeforeUnmount(() => {
  if (!added) letGo(held.value.map((h) => h.token))
})

const ready = computed(() => held.value.length > 0 && answer.value !== null && !!name.value.trim() && !!licence.value.trim() && mayGo.value !== null && !busy.value)
const lines = computed(() => (answer.value?.files ?? []).map((check) => ({ check, line: checkLine(check, t), description: checkDescription(check, t) })))
const scope = computed(() =>
  answer.value && mayGo.value
    ? scopeSentences({ adds: answer.value.adds, families: answer.value.families, server: props.server, mayGo: mayGo.value, accessSecretSet: props.accessSecretSet }, t)
    : [],
)

function tooMuch(): string {
  return tooMuchToAdd([], [{ size: props.limits.bytes + 1 }], props.limits, t)
}

function failed(e: unknown) {
  if (e instanceof AdminApiError && e.status === 503) error.value = tooMuch()
  else error.value = e instanceof AdminApiError ? e.message : t('Could not reach the server.')
}

/** Tells the server to let go of files that will not be added; nothing to wait for, and a failure only means they go
 *  after a while on their own. */
function letGo(tokens: string[]) {
  if (tokens.length) void adminApi.dropFontFiles(props.token, tokens).catch(() => undefined)
}

async function take(files: FileList | File[] | null) {
  if (!files || !files.length) return
  const chosen = Array.from(files)
  error.value = tooMuchToAdd(held.value, chosen, props.limits, t)
  if (error.value) return
  busy.value = true
  const batch: { token: string; name: string; size: number }[] = []
  try {
    for (const file of chosen) batch.push({ token: (await adminApi.holdFontFile(props.token, file, file.name)).token, name: file.name, size: file.size })
    answer.value = await adminApi.checkFonts(props.token, [...held.value, ...batch].map((h) => h.token))
    held.value = [...held.value, ...batch]
    if (!licence.value) licence.value = suggestedLicence(answer.value.files)
    if (licence.value && mayGo.value === null && /^(OFL|Apache|Ubuntu|LPPL)/.test(licence.value)) mayGo.value = 'anywhere'
    if (!name.value && answer.value.families.length === 1) name.value = answer.value.families[0]!
  } catch (e) {
    letGo(batch.map((h) => h.token)) // a batch is held whole or not at all
    failed(e)
  } finally {
    busy.value = false
  }
}

function picked(event: Event) {
  const input = event.target as HTMLInputElement
  void take(input.files).then(() => {
    input.value = '' // so the same files can be chosen again
  })
}

function dropped(event: DragEvent) {
  dragging.value = false
  void take(event.dataTransfer?.files ?? null)
}

function clear() {
  letGo(held.value.map((h) => h.token))
  held.value = []
  answer.value = null
  error.value = ''
}

async function add() {
  if (!ready.value || !mayGo.value) return
  busy.value = true
  error.value = ''
  try {
    const page = await adminApi.addFontCollection(props.token, { files: held.value.map((h) => h.token), name: name.value.trim(), licence: licence.value.trim(), may_go: mayGo.value })
    added = true // the server has used the files up
    emit('added', page)
  } catch (e) {
    failed(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Modal :title="t('Add fonts to {server}', { server })" :width="640" @close="emit('close')">
    <form v-if="step === 'choose'" class="form" @submit.prevent="step = 'check'">
      <fieldset>
        <legend>{{ t('From files') }}</legend>
        <div class="drop" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave="dragging = false" @drop.prevent="dropped">
          <template v-if="held.length">
            <p class="chosen">{{ held.length === 1 ? t('1 file chosen') : t('{n} files chosen', { n: held.length }) }}</p>
            <p class="names">{{ held.map((h) => h.name).join(', ') }}</p>
          </template>
          <label class="pick">
            {{ held.length ? t('Add more files…') : t('Choose files…') }}
            <input ref="picker" type="file" multiple accept=".ttf,.otf,.zip,font/ttf,font/otf,application/zip" class="sr-only" @change="picked" >
          </label>
          <span class="or">{{ t('or drop them here: TrueType, OpenType, or a .zip of them') }}</span>
          <button v-if="held.length" type="button" class="link" @click="clear">{{ t('Start again') }}</button>
        </div>
        <p v-if="busy" class="muted" role="status">{{ t('Checking the files…') }}</p>
      </fieldset>

      <label class="field">
        {{ t('Name of the collection') }}
        <input ref="nameField" v-model="name" autocomplete="off" required >
      </label>

      <fieldset class="who">
        <legend>{{ t('Who may receive these fonts') }}</legend>
        <label class="choice">
          <input v-model="mayGo" type="radio" name="may-go" value="anywhere" >
          <span>
            <span class="choice-name">{{ t('Anyone') }}</span>
            <span class="choice-sub">{{ t('An open licence. Handed to everyone who opens a document here.') }}</span>
          </span>
        </label>
        <label class="choice">
          <input v-model="mayGo" type="radio" name="may-go" value="this-server" >
          <span>
            <span class="choice-name">{{ t('People using this server') }}</span>
            <span class="choice-sub">{{ t('A licence for your organisation. Handed only to people who have this server’s access secret.') }}</span>
          </span>
        </label>
        <p v-if="mayGo === 'this-server' && !accessSecretSet" class="caution">
          {{ t('This server has no access secret, so everyone who can reach it counts as its people. Set one under Access & documents.') }}
        </p>
      </fieldset>

      <label class="field">
        {{ t('Licence, in your words') }}
        <input v-model="licence" autocomplete="off" required >
        <span class="hint">{{ answer && suggestedLicence(answer.files) ? t('Filled in from what the fonts say about themselves; change it if it is not right.') : t('Goes into the collection’s licence record, with your name and today’s date.') }}</span>
      </label>

      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="buttons">
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
        <button class="btn primary" type="submit" :disabled="!ready">{{ t('Check files') }}</button>
      </div>
    </form>

    <div v-else class="form">
      <p class="collection">
        <strong>{{ name }}</strong>
        <MayGoBadge v-if="mayGo" :may-go="mayGo" />
      </p>
      <ul class="checks">
        <li v-for="({ check, line, description }, i) in lines" :key="i" class="check" :class="line.tone">
          <div class="check-head">
            <span class="file">{{ check.name }}</span>
            <span class="verdict" :class="line.tone">{{ line.badge }}</span>
          </div>
          <div v-if="description" class="description">{{ description }}</div>
          <div v-if="line.note" class="note">{{ line.note }}</div>
        </li>
      </ul>
      <div v-if="answer?.adds" class="scope">
        <p v-for="(sentence, i) in scope" :key="i">{{ sentence }}</p>
      </div>
      <p v-else class="error">{{ t('None of these files is a font this server can use.') }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="buttons">
        <button class="btn" type="button" :disabled="busy" @click="step = 'choose'">{{ t('Back') }}</button>
        <button class="btn primary" type="button" :disabled="busy || !answer?.adds" @click="add">
          {{ answer?.adds === 1 ? t('Add 1 font') : t('Add {n} fonts', { n: answer?.adds ?? 0 }) }}
        </button>
      </div>
    </div>
  </Modal>
</template>

<style scoped>
.form {
  display: grid;
  gap: 14px;
  --ok-text: color-mix(in srgb, var(--teal) 72%, var(--text));
  --bad-text: color-mix(in srgb, var(--rose) 72%, var(--text));
  --warn-text: color-mix(in srgb, var(--apricot) 60%, var(--text));
  --own-text: color-mix(in srgb, var(--iris) 80%, var(--text));
}
fieldset {
  border: none;
  margin: 0;
  padding: 0;
}
legend,
.field {
  font: 600 13px var(--font-ui);
  margin-bottom: 6px;
}
.drop {
  border: 1.5px dashed color-mix(in srgb, var(--iris) 60%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--iris) 5%, transparent);
  padding: 14px 16px;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 10px;
}
.drop.dragging {
  background: color-mix(in srgb, var(--iris) 14%, transparent);
}
.chosen {
  flex-basis: 100%;
  margin: 0;
  font: 600 14px var(--font-ui);
}
.names {
  flex-basis: 100%;
  margin: 0 0 4px;
  font: 12.5px var(--font-mono);
  color: var(--muted);
  overflow-wrap: anywhere;
}
.pick {
  color: var(--own-text);
  font: 500 13px var(--font-ui);
  text-decoration: underline;
  cursor: pointer;
}
.pick:focus-within {
  outline: 2px solid var(--iris);
  outline-offset: 2px;
  border-radius: 4px;
}
.or,
.muted,
.hint {
  font: 12.5px var(--font-ui);
  color: var(--muted);
}
.link {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--own-text);
  text-decoration: underline;
  font: 12.5px var(--font-ui);
  cursor: pointer;
}
.field input {
  display: block;
  width: 100%;
  margin-top: 6px;
  padding: 9px 12px;
  border-radius: 9px;
  border: 1px solid var(--line-field);
  background: var(--surface);
  color: var(--text);
  font: 13px var(--font-ui);
}
.field .hint {
  display: block;
  margin-top: 6px;
  font-weight: 400;
}
.who {
  display: grid;
  gap: 8px;
}
.choice {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font: 13px var(--font-ui);
}
.choice input {
  margin-top: 3px;
}
.choice-name {
  display: block;
  font-weight: 500;
}
.choice-sub {
  display: block;
  color: var(--muted);
  font-size: 12.5px;
}
.caution {
  margin: 0;
  font-size: 12.5px;
  color: var(--warn-text);
}
.error {
  margin: 0;
  font-size: 13px;
  color: var(--bad-text);
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.collection {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
}
.checks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
  max-height: 320px;
  overflow: auto;
}
.check {
  border: 1px solid var(--line-field);
  border-radius: 10px;
  padding: 10px 14px;
}
.check.bad {
  background: color-mix(in srgb, var(--rose) 5%, transparent);
}
.check-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
.file {
  font: 13px var(--font-mono);
  overflow-wrap: anywhere;
}
.verdict {
  flex: none;
  border-radius: 999px;
  padding: 2px 9px;
  font: 500 12px var(--font-ui);
}
.verdict.ok {
  background: color-mix(in srgb, var(--teal) 14%, transparent);
  color: var(--ok-text);
}
.verdict.warn {
  background: color-mix(in srgb, var(--apricot) 18%, transparent);
  color: var(--warn-text);
}
.verdict.bad {
  background: color-mix(in srgb, var(--rose) 14%, transparent);
  color: var(--bad-text);
}
.description {
  margin-top: 3px;
  font-size: 12.5px;
  color: var(--muted);
}
.note {
  margin-top: 3px;
  font-size: 12.5px;
}
.check.bad .note {
  color: var(--bad-text);
}
.scope {
  border-radius: 10px;
  background: color-mix(in srgb, var(--apricot) 10%, transparent);
  padding: 12px 16px;
  font-size: 13px;
}
.scope p {
  margin: 0;
}
.scope p + p {
  margin-top: 6px;
}
</style>
