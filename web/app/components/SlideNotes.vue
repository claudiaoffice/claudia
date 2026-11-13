<script setup lang="ts">
// The speaker notes of the slide that is shown and its planned time (D342, D343): a Markdown field under the slide and a
// clock chip beside it. Both are document content, written like any other edit — one step in the history, for
// everybody, undoable — and read-only for a viewer. The notes show formatted in the presenter view only; never on the
// slide.
import { computed, nextTick, ref, watch } from 'vue'
import { PLAN_CHIPS, formatTime, parseTime, stepTime } from '~/lib/show-time'
import type { SlideSession } from '~/lib/slide-session'
import Popover from './Popover.vue'

const props = defineProps<{ session: SlideSession; hint?: string; t: (msgid: string, vars?: Record<string, string | number>) => string }>()
const { t } = props
const emit = defineEmits<{ present: [from: 'start' | 'here'] }>()
const session = props.session
const state = session.state

const draft = ref('')
const editing = ref<string | null>(null) // the slide whose notes are being written
const field = ref<HTMLTextAreaElement | null>(null)
const readonly = computed(() => session.readOnly)
const slide = computed(() => state.activeSlide)
const notes = computed(() => session.notesOf(slide.value))
const seconds = computed(() => session.secondsOf(slide.value))

// What the document says, unless the person is in the middle of writing: then a colleague's change waits for the
// blur (the same rule as everywhere else in the app: nothing changes under someone's hands).
watch(
  [slide, notes],
  () => {
    if (editing.value === null) draft.value = notes.value
  },
  { immediate: true },
)

function begin() {
  editing.value = slide.value
}
async function commit() {
  const was = editing.value
  editing.value = null
  if (was === null || readonly.value) return
  if (draft.value !== session.notesOf(was)) await session.setNotes(was, draft.value)
  if (editing.value === null) draft.value = session.notesOf(slide.value)
}

// ------------------------------------------------------------------------------ the planned time
const chip = ref<HTMLButtonElement | null>(null)
const open = ref<{ x: number; y: number } | null>(null)
const typed = ref('')
const bad = ref(false)

async function openTime() {
  const box = chip.value?.getBoundingClientRect()
  open.value = { x: box?.left ?? 24, y: (box?.bottom ?? 120) + 6 }
  typed.value = seconds.value === null ? '' : formatTime(seconds.value)
  bad.value = false
  await nextTick()
  document.querySelector<HTMLInputElement>('[data-testid="time-field"]')?.select()
}
function closeTime() {
  open.value = null
  chip.value?.focus()
}
/** What was last sent for this slide: Enter and the blur that follows it are one change, not two steps in the history. */
let sent: { slide: string; value: number | null } | null = null
watch([slide, seconds], () => (sent = null)) // the document has spoken: what it says counts again
async function plan(value: number | null) {
  if (readonly.value) return
  const was = sent?.slide === slide.value ? sent.value : seconds.value
  if (value === was) return
  sent = { slide: slide.value, value }
  if (await session.setTime(slide.value, value)) {
    typed.value = value === null ? '' : formatTime(value)
    bad.value = false
  } else sent = null
}
async function commitTyped() {
  if (typed.value.trim() === '') return plan(null)
  const value = parseTime(typed.value)
  bad.value = value === null
  if (value !== null) await plan(value)
}

defineExpose({ openTime, focus: () => field.value?.focus() })
</script>

<template>
  <section class="notes" data-testid="notes" :aria-label="t('Speaker notes')">
    <header>
      <label :for="`notes-${slide}`">{{ t('Speaker notes') }}</label>
      <span class="hint">{{ t('Markdown: **bold**, *italic*, - lists. Shown in the presenter view, never on the slide.') }}</span>
      <button
        ref="chip"
        type="button"
        class="chip"
        data-testid="time-chip"
        :aria-label="seconds === null ? t('Plan a time for this slide') : t('Planned time for this slide: {time}', { time: formatTime(seconds) })"
        :aria-expanded="open !== null"
        aria-haspopup="dialog"
        @click="open ? closeTime() : openTime()"
      >
        <span aria-hidden="true">⏱</span>
        <span class="mono">{{ seconds === null ? t('Plan time') : formatTime(seconds) }}</span>
        <kbd v-if="hint" aria-hidden="true">{{ hint }}</kbd>
      </button>
    </header>
    <textarea
      :id="`notes-${slide}`"
      ref="field"
      v-model="draft"
      data-testid="notes-field"
      rows="3"
      :readonly="readonly"
      :placeholder="readonly ? '' : t('What to say on this slide')"
      @focus="begin"
      @blur="commit"
      @keydown.f5.prevent="emit('present', $event.shiftKey ? 'here' : 'start')"
      @keydown.esc.stop="($event.target as HTMLElement).blur()"
    />
    <Popover v-if="open" :x="open.x" :y="open.y" :label="t('Planned time')" :width="300" :anchor="chip" @close="closeTime">
      <div class="time" data-testid="time-popover">
        <div class="chips" role="group" :aria-label="t('Common times')">
          <button
            v-for="s in PLAN_CHIPS"
            :key="s"
            type="button"
            :aria-pressed="seconds === s"
            :disabled="readonly"
            :data-testid="`time-chip-${s / 60}`"
            @click="plan(s)"
          >
            {{ t('{n} min', { n: s / 60 }) }}
          </button>
        </div>
        <div class="entry">
          <button type="button" :disabled="readonly || seconds === null" :aria-label="t('Less time')" data-testid="time-less" @click="plan(stepTime(seconds, -1))">−</button>
          <input
            v-model="typed"
            data-testid="time-field"
            class="mono"
            inputmode="text"
            :readonly="readonly"
            :aria-label="t('Planned time, for example 2, 2:30 or 90s')"
            :aria-invalid="bad"
            @keydown.enter.prevent="commitTyped"
            @blur="commitTyped"
          >
          <button type="button" :disabled="readonly" :aria-label="t('More time')" data-testid="time-more" @click="plan(stepTime(seconds, 1))">+</button>
          <button type="button" class="clear" :disabled="readonly || seconds === null" data-testid="time-clear" @click="plan(null)">{{ t('Clear') }}</button>
        </div>
        <p v-if="bad" class="problem" role="alert">{{ t('Try 2 for two minutes, 2:30 or 90s.') }}</p>
      </div>
    </Popover>
  </section>
</template>

<style scoped>
.notes {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 12px 10px;
  background: var(--surface);
  border-top: 1px solid var(--line);
}
header {
  display: flex;
  align-items: center;
  gap: 12px;
}
label {
  font-weight: 500;
  font-size: 13px;
}
.hint {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
textarea {
  resize: vertical;
  min-height: 54px;
  max-height: 40vh;
  padding: 8px 10px;
  font: inherit;
  font-size: 14px;
  line-height: 1.4;
  color: var(--text);
  background: var(--paper);
  border: 1px solid var(--line-field);
  border-radius: 8px;
}
textarea:focus-visible {
  outline: 2px solid var(--app);
  outline-offset: 1px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  font-size: 13px;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--line-field);
  border-radius: 999px;
}
.chip[aria-expanded='true'] {
  background: var(--app-soft);
  color: var(--app-dark);
}
.chip kbd {
  font-size: 11px;
  padding: 0 5px;
  border: 1px solid var(--line);
  border-radius: 4px;
  color: var(--muted);
}
.time {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 6px;
}
.chips,
.entry {
  display: flex;
  gap: 6px;
  align-items: center;
}
.chips button,
.entry button {
  padding: 4px 10px;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
}
.chips button[aria-pressed='true'] {
  background: var(--app-soft);
  color: var(--app-dark);
  border-color: var(--app);
}
.entry input {
  width: 5.5em;
  padding: 4px 8px;
  text-align: center;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  background: var(--paper);
  color: var(--text);
}
.entry input[aria-invalid='true'] {
  border-color: #b3261e;
}
.clear {
  margin-inline-start: auto;
}
.problem {
  margin: 0;
  font-size: 12px;
  color: #b3261e;
}
button:disabled {
  opacity: 0.45;
}
</style>
