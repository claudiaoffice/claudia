<script setup lang="ts">
// One suggestion of the assistant, opened where it is marked in the text (D63, D262). The list that stood above the
// panel's tabs was taken out at the owner's request (2026-11-12): a suggestion is reviewed where it is, by clicking
// its mark, or from the count in the bottom bar. Nothing is written until a person accepts; the accepter is the
// author of the new text, and the suggestion's author is remembered with it.
import { computed } from 'vue'
import type { TextSession } from '~/lib/text-session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ session: TextSession; id: string; x: number; y: number }>()
const emit = defineEmits<{ close: []; next: [] }>()

const state = props.session.state
const open = computed(() => state.suggestions.filter((s) => s.state === 'open'))
const s = computed(() => open.value.find((x) => x.id === props.id) ?? null)
const others = computed(() => open.value.length - (s.value ? 1 : 0))

/** After a decision: on to the next one if there is one, else close. */
function onward() {
  if (others.value) emit('next')
  else emit('close')
}
async function accept() {
  if (s.value && (await props.session.accept(s.value.id))) onward()
}
async function reject() {
  if (s.value && (await props.session.reject(s.value.id))) onward()
}
</script>

<template>
  <Popover v-if="s" :x="x" :y="y" :width="320" :label="t('Suggestion')" @close="emit('close')">
    <div class="suggestion" :class="{ outdated: s.outdated }" data-testid="suggestion" :data-suggestion="s.id">
      <p class="who">{{ t('{author} suggests', { author: s.author ?? 'ai' }) }}</p>
      <p class="reason">{{ s.reason }}</p>
      <p v-if="s.replacement !== null" class="change">
        <del>{{ s.original || '·' }}</del> <span class="arrow" aria-hidden="true">→</span> <ins>{{ s.replacement || t('(delete)') }}</ins>
      </p>
      <p v-else class="change remark">“{{ s.original.length > 60 ? s.original.slice(0, 60) + '…' : s.original }}”</p>
      <p v-if="s.outdated" class="note">{{ t('The text under it changed. It cannot be accepted any more.') }}</p>
      <div class="buttons">
        <button v-if="s.replacement !== null" type="button" class="accept" :disabled="s.outdated || session.readOnly" @click="accept">{{ t('Accept') }}</button>
        <button type="button" class="reject" :disabled="session.readOnly" @click="reject">{{ s.replacement === null ? t('Dismiss') : t('Reject') }}</button>
        <button v-if="others" type="button" class="next" data-testid="next-suggestion" @click="emit('next')">{{ t('Next ({others})', { others }) }}</button>
      </div>
    </div>
  </Popover>
</template>

<style scoped>
.suggestion {
  display: grid;
  gap: 6px;
}
.suggestion.outdated .change {
  opacity: 0.6;
}
p {
  margin: 0;
}
.who {
  font: 500 11px var(--font-ui);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
}
.reason {
  font-size: 13px;
  color: var(--text);
}
.change {
  font-size: 15px;
}
del {
  color: var(--muted);
}
ins {
  text-decoration: none;
  font-weight: 600;
  color: var(--text);
}
.arrow {
  color: var(--muted);
}
.remark {
  font-style: italic;
  color: var(--muted);
}
.note {
  font-size: 12px;
  color: var(--app-text, var(--text));
}
.buttons {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}
button {
  border: 1px solid var(--line-field);
  background: transparent;
  color: var(--text);
  border-radius: 999px;
  padding: 4px 13px;
  font: 500 12.5px var(--font-ui);
  cursor: pointer;
}
button:hover:not(:disabled) {
  background: var(--faint);
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
button.accept {
  background: var(--app-dark);
  border-color: var(--app-dark);
  color: #fff;
}
button.next {
  margin-left: auto;
  border-color: transparent;
  color: var(--muted);
}
</style>
