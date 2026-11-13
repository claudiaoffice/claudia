<script setup lang="ts">
// Format ▸ Describe Object… (BITV 1.1.1, UX alt text): what a picture, a chart, a shape or a text box shows to
// someone who cannot see it — or the mark that it is only decoration, which a screen reader then skips. The same
// dialog in computes and creates; what is sent and checked is `lib/descriptions.ts`, which mirrors the server.
import { computed, ref } from 'vue'
import { MAX_DESCRIPTION, describeParams, descriptionProblem, type Describable } from '~/lib/descriptions'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  /** The object being described: its kind decides whether an empty description is a problem (a picture needs one). */
  object: Describable
  /** The words as they stand, for the field to start from (the effective alt text, not only what was typed). */
  current: string
}>()
const emit = defineEmits<{ close: []; save: [params: { description: string; decorative: boolean }] }>()

// Ticking "Decorative" greys the words out rather than deleting them, so unticking brings back what was typed.
const text = ref(props.object.decorative ? '' : props.current)
const decorative = ref(props.object.decorative)

const problem = computed(() => descriptionProblem(props.object.kind, text.value, decorative.value))
const message = computed(() => {
  switch (problem.value) {
    case 'empty':
      return t('Describe the picture, or tick "Decorative" if it adds nothing a reader would miss.')
    case 'too-long':
      return t('At most {max} characters.', { max: MAX_DESCRIPTION })
    default:
      return ''
  }
})
const counter = computed(() => t('{count} of {max} characters', { count: text.value.length, max: MAX_DESCRIPTION }))

function submit() {
  if (problem.value) return
  emit('save', describeParams(text.value, decorative.value))
}
</script>

<template>
  <Modal :title="t('Describe object')" :width="460" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <label class="field">
        {{ t('Description (read aloud to someone who cannot see it)') }}
        <textarea
          v-model="text"
          rows="4"
          :maxlength="MAX_DESCRIPTION * 2"
          :disabled="decorative"
          :aria-invalid="problem === 'empty' || problem === 'too-long'"
          aria-describedby="describe-counter describe-problem"
          autofocus
        />
      </label>
      <p id="describe-counter" class="counter" :class="{ over: problem === 'too-long' }">{{ counter }}</p>
      <label class="check">
        <input v-model="decorative" type="checkbox" >
        {{ t('Decorative: only for looks, a screen reader skips it') }}
      </label>
      <p id="describe-problem" class="error" role="alert">{{ message }}</p>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="problem !== null">{{ t('Save') }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.form {
  display: grid;
  gap: 12px;
}
.field {
  display: grid;
  gap: 6px;
}
textarea {
  font: inherit;
  resize: vertical;
}
.counter {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.counter.over {
  color: var(--rose);
}
.check {
  display: flex;
  gap: 8px;
  align-items: center;
}
.error {
  margin: 0;
  min-height: 1.2em;
  color: var(--rose);
  font-size: 13px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
