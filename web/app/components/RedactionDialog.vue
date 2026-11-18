<script setup lang="ts">
// Redact… (E3.14; D720–D728, mock-ups `notes/mockups/redaction-0*.svg`): what goes, what goes with it, what it means, and
// a button that names the scope. The plan is worked out on the server and shown before anything changes (D721); the
// document behind the dialog shows the state it would leave, with the places marked (the session's preview). An editor
// whose redaction reaches somebody else's work is told whose, and can ask an owner instead (D727). An import is
// blanked whole or in parts the person picks in the document (D723, D728). Nothing here decides who may do what:
// `lib/redaction.ts` does, and the server checks it again.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { clock, colorOf } from '~/lib/people'
import { useI18n } from '~/lib/i18n'
import {
  askOwnerNote,
  itemCount,
  noteFor,
  partsWords,
  pickedCount,
  splitSteps,
  togglingEntry,
  togglingMessage,
  withParts,
  type Picked,
  type RedactionPlan,
} from '~/lib/redaction'

const { t } = useI18n()

const props = defineProps<{ session: BaseSession; picked: Picked }>()
const emit = defineEmits<{ close: []; done: [] }>()
const state = props.session.state

const picked = ref<Picked>(props.picked)
const plan = ref<RedactionPlan | null>(null)
/** Why the plan could not be worked out, said in the dialog itself. */
const problem = ref('')
const busy = ref(false)
const working = ref(false)
/** The chat note to the people whose work goes (D728): on by default, the person may change or untick it. */
const noteOn = ref(true)
const note = ref('')
const noteEdited = ref(false)

const count = computed(() => (plan.value ? itemCount(plan.value) : 0))
const steps = computed(() => (plan.value ? splitSteps(plan.value) : { picked: [], following: [] }))
const messages = computed(() => (plan.value?.chat ?? []).map((n) => state.chat.find((m) => m.number === n)).filter((m) => m !== undefined))
const blocked = computed(() => plan.value !== null && !plan.value.allowed)
const askNote = computed(() => (plan.value && blocked.value ? askOwnerNote(plan.value, state.chat, t, clock) : ''))
const title = computed(() => t('Redact for good'))
const canRedact = computed(() => plan.value !== null && plan.value.allowed && count.value > 0 && !busy.value && !working.value)

/** Work the plan out again for what is picked now; the preview follows. */
async function replan() {
  if (!pickedCount(picked.value)) {
    plan.value = null
    await props.session.endPreview()
    return
  }
  working.value = true
  const found = await props.session.planRedaction(picked.value)
  working.value = false
  if (typeof found === 'string') {
    problem.value = found
    plan.value = null
    await props.session.endPreview()
    return
  }
  problem.value = ''
  plan.value = found
  if (!noteEdited.value) note.value = noteFor(found, state.chat, state.me, t)
  await props.session.previewRedaction(found)
}
onMounted(replan)
onBeforeUnmount(() => void props.session.endPreview())
// somebody worked in the meantime: the plan, its dependents and the preview may be different now (D726, D727)
watch(
  () => state.revision,
  () => {
    if (!busy.value && !pickingParts.value) void replan()
  },
)

function untickStep(revision: string) {
  picked.value = togglingEntry(picked.value, revision)
  void replan()
}
function untickMessage(number: number) {
  picked.value = togglingMessage(picked.value, number)
  void replan()
}
function onNoteInput(event: Event) {
  note.value = (event.target as HTMLInputElement).value
  noteEdited.value = true
}

async function redact() {
  if (!plan.value || !canRedact.value) return
  busy.value = true
  const done = await props.session.redact(picked.value, plan.value, noteOn.value ? note.value : '')
  busy.value = false
  if (done) emit('done')
  else void replan() // the server said why; show the plan as it is now
}
async function askAnOwner() {
  if (askNote.value && (await props.session.say(askNote.value))) {
    props.session.notice(t('Your request went to the chat.'))
    emit('close')
  }
}
/** Ctrl+Enter redacts; Enter alone never does (D728). */
function onKey(event: KeyboardEvent) {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    void redact()
  }
}

// ------------------------------------------------------------------------------ an import, whole or in parts (D723)
const pickingParts = ref<string | null>(null)
const partsOf = (revision: string) => picked.value.parts?.[revision] ?? null
const words = computed(() => partsWords(plan.value?.app ?? state.app, t))
const rangeText = ref('')
const rangeError = ref('')

function setWhole(revision: string, whole: boolean) {
  picked.value = withParts(picked.value, revision, whole ? null : (partsOf(revision) ?? []))
  if (whole || partsOf(revision)?.length) void replan()
}
/** "Pick in the document…": the dialog steps aside, a click on a paragraph, a slide, a sheet tab or an object takes it
 * in or out, and "Done" brings the dialog back with the plan worked out again. */
async function startPickingParts(revision: string) {
  pickingParts.value = revision
  await props.session.endPreview() // the person picks in what is there, not in the blanked preview
}
/** What a picked part is called in the dialog, read when it is picked (the preview shows it blanked afterwards). */
const partLabels = ref<Record<string, string>>({})
function labelOf(id: string): string {
  const named = props.session.nameOf(id)
  if (named) return named
  const el = document.querySelector(`[data-thing="${CSS.escape(id)}"], [data-block="${CSS.escape(id)}"]`)
  const words = el?.textContent?.trim().replace(/\s+/g, ' ') ?? ''
  return words ? (words.length > 28 ? `${words.slice(0, 27)}…` : words) : id
}
function togglePart(id: string) {
  const revision = pickingParts.value
  if (!revision) return
  partLabels.value = { ...partLabels.value, [id]: labelOf(id) }
  const now = partsOf(revision) ?? []
  picked.value = withParts(picked.value, revision, now.includes(id) ? now.filter((p) => p !== id) : [...now, id])
}
function addRange() {
  const revision = pickingParts.value ?? plan.value?.imports[0]
  const part = revision ? props.session.redactionRangePart(rangeText.value) : null
  if (!revision || !part) {
    rangeError.value = t('Write a range like A1:B5.')
    return
  }
  rangeError.value = ''
  rangeText.value = ''
  const now = partsOf(revision) ?? []
  if (!now.includes(part)) picked.value = withParts(picked.value, revision, [...now, part])
  if (!pickingParts.value) void replan()
}
function removePart(revision: string, part: string) {
  picked.value = withParts(picked.value, revision, (partsOf(revision) ?? []).filter((p) => p !== part))
  void replan()
}
function donePicking() {
  pickingParts.value = null
  void replan()
}
function partName(part: string): string {
  const at = part.indexOf('!')
  if (at > 0) return `${props.session.nameOf(part.slice(0, at)) ?? part.slice(0, at)}!${part.slice(at + 1)}`
  return partLabels.value[part] ?? props.session.nameOf(part) ?? part
}
const pickedParts = computed(() => (pickingParts.value ? (partsOf(pickingParts.value) ?? []) : []))

/** The thing under a click while picking parts: a named thing (slide, sheet tab, object) or a paragraph. */
function partAt(target: EventTarget | null): string | null {
  const el = (target as HTMLElement | null)?.closest?.('[data-thing], [data-block]') as HTMLElement | null
  if (!el || el.closest('.partsBar')) return null
  return el.getAttribute('data-thing') ?? el.getAttribute('data-block')
}
function onPartClick(event: MouseEvent) {
  if (!pickingParts.value) return
  const id = partAt(event.target)
  if (!id) return
  event.preventDefault()
  event.stopImmediatePropagation()
  togglePart(id)
}
function onPartPress(event: Event) {
  if (pickingParts.value && partAt(event.target)) {
    event.preventDefault()
    event.stopImmediatePropagation()
  }
}
/** What is picked is outlined in the document itself, not by colour alone: a thick outline and an offset. */
const partStyle = computed(() =>
  pickedParts.value.length
    ? pickedParts.value
        .map((id) => `[data-thing="${CSS.escape(id)}"], [data-block="${CSS.escape(id)}"]`)
        .join(', ') + ' { outline: 3px solid var(--iris) !important; outline-offset: 2px; }'
    : '',
)
let styleEl: HTMLStyleElement | null = null
watch(partStyle, (css) => {
  styleEl ??= document.head.appendChild(document.createElement('style'))
  styleEl.textContent = css
})
onMounted(() => {
  window.addEventListener('click', onPartClick, true)
  for (const type of ['pointerdown', 'mousedown', 'dblclick']) window.addEventListener(type, onPartPress, true)
})
onBeforeUnmount(() => {
  window.removeEventListener('click', onPartClick, true)
  for (const type of ['pointerdown', 'mousedown', 'dblclick']) window.removeEventListener(type, onPartPress, true)
  styleEl?.remove()
})
</script>

<template>
  <Modal v-if="!pickingParts" :title="title" :width="640" @close="emit('close')">
    <div class="body" data-testid="redaction-dialog" @keydown="onKey">
      <p class="where"><span class="dot" aria-hidden="true" />{{ t('{doc} on {host}', { doc: state.doc, host: state.host || t('this computer') }) }}</p>

      <p v-if="problem" class="problem" role="alert">{{ t('This cannot be redacted: {why}', { why: problem }) }}</p>
      <p v-else-if="!plan && !working" class="lead">{{ t('Nothing is picked. Pick changes or messages in History & Chat.') }}</p>
      <p v-if="working && !plan" class="lead" role="status">{{ t('Working it out…') }}</p>

      <template v-if="plan">
        <section aria-labelledby="red-picked">
          <h3 id="red-picked">{{ t('What you picked') }}</h3>
          <ul class="items">
            <li v-for="s in steps.picked" :key="s.revision">
              <input type="checkbox" checked :aria-label="t('Keep {what} in the redaction', { what: s.summary })" @change="untickStep(s.revision)">
              <span class="who" :style="{ background: colorOf(state, s.author ?? '') }">{{ (s.author ?? '?').slice(0, 1).toUpperCase() }}</span>
              <span class="what mono" :title="s.label">{{ s.summary }}</span>
              <time>{{ clock(s.time) }}</time>
            </li>
            <li v-for="m in messages" :key="'m' + m!.number">
              <input type="checkbox" checked :aria-label="t('Keep the message at {time} in the redaction', { time: clock(m!.time) })" @change="untickMessage(m!.number)">
              <span class="who" :style="{ background: colorOf(state, m!.author) }">{{ m!.author.slice(0, 1).toUpperCase() }}</span>
              <span class="what mono">{{ t('chat: {text}', { text: m!.text }) }}</span>
              <time>{{ clock(m!.time) }}</time>
            </li>
          </ul>
        </section>

        <section v-for="revision in plan.imports" :key="revision" class="import" :aria-label="t('The import')">
          <label class="choice"><input type="radio" :name="'whole-' + revision" :checked="partsOf(revision) === null" @change="setWhole(revision, true)"> {{ t('Everything that was imported') }}</label>
          <label class="choice"><input type="radio" :name="'whole-' + revision" :checked="partsOf(revision) !== null" @change="setWhole(revision, false)"> {{ t('Only what I pick: {what}', { what: words }) }}</label>
          <template v-if="partsOf(revision) !== null">
            <ul v-if="partsOf(revision)!.length" class="parts">
              <li v-for="part in partsOf(revision)" :key="part">{{ partName(part) }} <button type="button" class="linkish" :aria-label="t('Take {name} out', { name: partName(part) })" @click="removePart(revision, part)">×</button></li>
            </ul>
            <div class="partTools">
              <button type="button" class="btn" @click="startPickingParts(revision)">{{ t('Pick in the document…') }}</button>
              <template v-if="plan.app === 'computes'">
                <input v-model="rangeText" class="range" :placeholder="t('A1:B5')" :aria-label="t('Cells on the sheet on show')" @keydown.enter.prevent="addRange">
                <button type="button" class="btn" @click="addRange">{{ t('Add cells') }}</button>
                <span v-if="rangeError" class="error" role="alert">{{ rangeError }}</span>
              </template>
            </div>
          </template>
          <p class="hint">{{ t('The kept original file goes either way: it holds the same content.') }}</p>
        </section>

        <section v-if="steps.following.length" class="following" :class="{ blocked }" :aria-labelledby="'red-following'">
          <h3 id="red-following">{{ blocked ? t('This would also blank work by {names}', { names: plan.others.join(', ') }) : t('Goes with it, because it needs what you picked') }}</h3>
          <ul class="items">
            <li v-for="s in steps.following" :key="s.revision">
              <span class="who" :style="{ background: colorOf(state, s.author ?? '') }">{{ (s.author ?? '?').slice(0, 1).toUpperCase() }}</span>
              <span class="what mono" :title="s.label">{{ s.summary }}</span>
              <time>{{ clock(s.time) }}</time>
            </li>
          </ul>
          <p v-if="blocked">{{ t('You can redact only your own work. Untick what these steps need, or ask an owner to redact all of it.') }}</p>
          <p v-else>{{ t('Without what you picked, these steps no longer work, so they are blanked too.') }}</p>
        </section>

        <section v-if="!blocked" aria-labelledby="red-means">
          <h3 id="red-means">{{ t('What this means') }}</h3>
          <ul class="facts">
            <li class="strong">{{ t('Nobody can bring it back: not you, not the server, not undo.') }}</li>
            <li>{{ plan.changes_now ? t('The document changes now: the marked places show filler (the document behind this dialog is the preview).') : t('Nothing anybody sees in the document changes: it is only in the history.') }}</li>
            <li>{{ t('Everybody sees that you redacted something, how much and when, never what it held. How long each piece was stays visible.') }}</li>
            <li>{{ t('Copies, downloads, exports and backups made before keep it.') }}</li>
          </ul>
        </section>

        <section v-if="!blocked && note" class="note">
          <label class="choice"><input v-model="noteOn" type="checkbox"> {{ t('Tell them in the chat:') }}</label>
          <input class="noteText" :value="note" :disabled="!noteOn" :aria-label="t('The message to the chat')" @input="onNoteInput">
        </section>
        <section v-if="blocked" class="note">
          <p class="label">{{ t('Ask an owner in the chat:') }}</p>
          <p class="noteText asked">{{ askNote }}</p>
        </section>
      </template>

      <div class="buttons">
        <span class="role">{{ state.me.role === 'owner' ? t('You are an owner.') : t('You are an editor.') }}</span>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
        <button v-if="blocked" class="btn primary" type="button" @click="askAnOwner">{{ t('Ask an owner') }}</button>
        <button v-else class="btn redact" type="button" :disabled="!canRedact" :title="t('Ctrl+Enter')" @click="redact">{{ t('Redact ({n})', { n: count }) }}</button>
      </div>
    </div>
  </Modal>

  <div v-else class="partsBar" role="dialog" :aria-label="t('Pick what to blank')" data-testid="redaction-parts">
    <span role="status">{{ t('Click {what} in the document to pick them · {n} picked', { what: words, n: pickedParts.length }) }}</span>
    <template v-if="state.app === 'computes'">
      <input v-model="rangeText" class="range" :placeholder="t('A1:B5')" :aria-label="t('Cells on the sheet on show')" @keydown.enter.prevent="addRange">
      <button type="button" class="btn" @click="addRange">{{ t('Add cells') }}</button>
      <span v-if="rangeError" class="error" role="alert">{{ rangeError }}</span>
    </template>
    <button type="button" class="btn primary" @click="donePicking">{{ t('Done') }}</button>
  </div>
</template>

<style scoped>
.body {
  display: grid;
  gap: 14px;
}
.where {
  justify-self: start;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: -6px 0 0;
  padding: 3px 12px;
  border-radius: 999px;
  background: var(--ink);
  color: var(--paper);
  font-size: 12px;
}
.where .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #2f9e6b;
}
.lead {
  margin: 0;
  color: var(--muted);
}
.problem {
  margin: 0;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid color-mix(in srgb, var(--rose) 45%, transparent);
  background: color-mix(in srgb, var(--rose) 10%, transparent);
}
section {
  display: grid;
  gap: 6px;
}
h3 {
  margin: 0;
  font: 600 13px var(--font-ui);
}
.items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
}
.items li {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
}
.following .items li {
  grid-template-columns: auto minmax(0, 1fr) auto;
}
.who {
  display: inline-grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  color: #fff;
  font: 700 10px var(--font-ui);
}
.what {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}
time {
  color: var(--muted);
  font-size: 11px;
}
.following {
  padding: 10px 12px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--apricot) 16%, transparent);
  border: 1px solid color-mix(in srgb, var(--apricot) 45%, transparent);
}
.following.blocked {
  background: color-mix(in srgb, var(--rose) 12%, transparent);
  border-color: color-mix(in srgb, var(--rose) 45%, transparent);
}
.following p {
  margin: 0;
  font-size: 12px;
}
.facts {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 4px;
  font-size: 12.5px;
}
.facts .strong {
  font-weight: 600;
}
.import {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--line-field);
}
.choice {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
}
.parts {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.parts li {
  padding: 2px 4px 2px 10px;
  border-radius: 999px;
  background: var(--mist);
  color: var(--ink);
  font-size: 12px;
}
.linkish {
  border: 0;
  background: none;
  color: inherit;
}
.partTools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.range {
  width: 90px;
}
.hint {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.error {
  color: var(--rose);
  font-size: 12px;
}
.note .noteText {
  width: 100%;
  box-sizing: border-box;
}
.note .label,
.note .asked {
  margin: 0;
  font-size: 12.5px;
}
.note .asked {
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--line-field);
}
.buttons {
  display: flex;
  align-items: center;
  gap: 10px;
}
.role {
  margin-right: auto;
  color: var(--muted);
  font-size: 12px;
}
/* A document-level act that cannot be undone: the same red as deleting a document (DeleteDocumentDialog.vue). */
.btn.redact {
  background: var(--rose);
  border-color: var(--rose);
  color: #fff;
}
.partsBar {
  position: fixed;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%);
  z-index: 50;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  max-width: calc(100vw - 32px);
  padding: 10px 14px;
  border-radius: 14px;
  background: var(--surface);
  color: var(--text);
  border: 2px solid var(--iris);
  box-shadow: var(--shadow);
  font-size: 12.5px;
}
</style>
