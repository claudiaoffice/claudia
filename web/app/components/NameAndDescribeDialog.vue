<script setup lang="ts">
// Name & describe… (D1317, BITV 1.1.1): the one dialog for the name of a thing and what it shows to someone who cannot
// see it — or the mark that it is only decoration, which a screen reader then skips. The same in all three apps and for
// everything that can be pointed at: a paragraph, a table, a picture, a chart, a slide's text box. A heading is called
// by its words (the name is shown locked); a table or a range without a name asks for one. What is checked and sent is
// `lib/name-and-describe.ts`, which mirrors the server.
import { computed, ref } from 'vue'
import { MAX_DESCRIPTION } from '~/lib/descriptions'
import { useI18n } from '~/lib/i18n'
import { checkNameAndDescribe, type NameAndDescribeForm, type ThingDetails } from '~/lib/name-and-describe'

const { t } = useI18n()

const props = defineProps<{ details: ThingDetails }>()
const emit = defineEmits<{ close: []; save: [form: NameAndDescribeForm] }>()

// Ticking "Decorative" greys the words out rather than deleting them, so unticking brings back what was typed.
const name = ref(props.details.name)
const text = ref(props.details.decorative ? '' : props.details.description)
const decorative = ref(props.details.decorative)

const needsName = computed(() => props.details.id === '')
const problems = computed(() => checkNameAndDescribe(props.details, { name: name.value, description: text.value, decorative: decorative.value }))
const blocked = computed(() => problems.value.name !== null || problems.value.description !== null || (needsName.value && name.value.trim() === ''))
const counter = computed(() => t('{count} of {max} characters', { count: text.value.length, max: MAX_DESCRIPTION }))

function submit() {
  if (blocked.value) return
  emit('save', { name: name.value, description: text.value, decorative: decorative.value })
}
</script>

<template>
  <Modal :title="t('Name & describe')" :width="460" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <label class="field">
        {{ t('Name (what a tag in the chat points at)') }}
        <input
          v-model="name"
          type="text"
          :readonly="details.name_fixed"
          :aria-invalid="problems.name !== null"
          :aria-required="needsName"
          aria-describedby="name-note name-problem"
          autofocus
        >
      </label>
      <p id="name-note" class="note">{{ details.name_fixed ? t('A heading is called by its words.') : needsName ? t('Cells need a name before they can be described.') : '' }}</p>
      <p id="name-problem" class="error" role="alert">{{ problems.name ?? '' }}</p>
      <label class="field">
        {{ t('Description (read aloud to someone who cannot see it)') }}
        <textarea
          v-model="text"
          rows="4"
          :maxlength="MAX_DESCRIPTION * 2"
          :disabled="decorative"
          :aria-invalid="problems.description !== null"
          aria-describedby="describe-counter describe-problem"
        />
      </label>
      <p id="describe-counter" class="counter" :class="{ over: text.length > MAX_DESCRIPTION }">{{ counter }}</p>
      <label v-if="details.drawn" class="check">
        <input v-model="decorative" type="checkbox">
        {{ t('Decorative: only for looks, a screen reader skips it') }}
      </label>
      <p id="describe-problem" class="error" role="alert">{{ problems.description ?? '' }}</p>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="blocked">{{ t('Save') }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.form {
  display: grid;
  gap: 10px;
}
.field {
  display: grid;
  gap: 6px;
}
input[type='text'],
textarea {
  font: inherit;
}
input[readonly] {
  background: var(--panel, transparent);
  color: var(--muted);
}
textarea {
  resize: vertical;
}
.note,
.counter {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.note:empty {
  display: none;
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
