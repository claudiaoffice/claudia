<script setup lang="ts">
// File ▸ New for slides (E10.4, E10.22, D1538; board `notes/mockups/creates-templates-new-and-server.svg`, panel K): pick a
// template, or start from nothing. Each card says what the template is for, how many layouts it has and in which
// language; the built-in one comes first and is chosen. The template is copied into the new presentation, and nothing
// follows it. Only asked where there is something to choose from (`needsChoice`).
import { onMounted, ref } from 'vue'
import { useI18n } from '~/lib/i18n'
import { cardMeta, createLabel, type TemplateCard } from '~/lib/templates'

const { t } = useI18n()

const props = defineProps<{ templates: TemplateCard[]; busy: boolean; error: string }>()
const emit = defineEmits<{ create: [id: string]; close: [] }>()

const chosen = ref(props.templates[0]?.id ?? '')
const first = ref<HTMLInputElement | null>(null)

onMounted(() => first.value?.focus())

function create() {
  if (chosen.value) emit('create', chosen.value)
}
</script>

<template>
  <Modal :title="t('New presentation')" :width="760" @close="emit('close')">
    <form @submit.prevent="create">
      <fieldset class="cards">
        <legend class="sr-only">{{ t('Template') }}</legend>
        <label v-for="(card, i) in templates" :key="card.id" class="card" :class="{ on: chosen === card.id }">
          <input :ref="i === 0 ? 'first' : undefined" v-model="chosen" type="radio" name="template" :value="card.id" class="sr-only" >
          <span class="name">{{ card.name }}</span>
          <span class="purpose">{{ card.purpose }}</span>
          <span class="meta">{{ cardMeta(card, t) }}</span>
        </label>
      </fieldset>
      <p class="hint">{{ t('The template is copied into the new presentation. Later changes to the template never reach it.') }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="busy || !chosen">
          {{ createLabel(templates.find((c) => c.id === chosen) ?? templates[0]!, t) }}
        </button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.cards {
  border: none;
  margin: 0 0 12px;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 12px;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 130px;
  padding: 14px 16px;
  border: 1px solid var(--line-field);
  border-radius: 12px;
  background: var(--surface);
  cursor: pointer;
}
.card.on {
  border: 2px solid var(--ink);
  padding: 13px 15px;
  background: color-mix(in srgb, var(--line) 40%, var(--surface));
}
.card:has(input:focus-visible) {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
}
.name {
  font: 600 15px var(--font-display);
}
.purpose {
  font-size: 13px;
  flex: 1 1 auto;
}
.meta {
  font-size: 12.5px;
  color: var(--muted);
}
.hint {
  margin: 0 0 12px;
  font-size: 12.5px;
  color: var(--muted);
}
.error {
  margin: 0 0 12px;
  font-size: 13px;
  color: color-mix(in srgb, var(--rose) 72%, var(--text));
}
.buttons {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
</style>
