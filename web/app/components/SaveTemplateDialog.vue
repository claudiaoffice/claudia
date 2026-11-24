<script setup lang="ts">
// Format ▸ Template ▸ Save as Template… (E10.4, E10.22, D1537; board `notes/mockups/creates-templates-new-and-server.svg`,
// panel N): a Claudia export of this presentation without its slides, with a note of what it is called, what it is for
// and in which language. Anyone can make one; only a server's administrator adds it to the server (Server settings ▸
// Templates). The server records the saving as an export, as any other.
import { computed, onMounted, ref } from 'vue'
import type { SlideSession } from '~/lib/slide-session'
import { downloadBase64 } from '~/lib/download'
import { languageNow, useI18n } from '~/lib/i18n'
import { languageChoices, MAX_NAME, MAX_PURPOSE, noteProblem } from '~/lib/template-change'

const { t } = useI18n()

const props = defineProps<{ session: SlideSession }>()
const emit = defineEmits<{ close: [] }>()

const name = ref('')
const purpose = ref('')
const language = ref(languageNow())
const busy = ref(false)
const problem = ref('')
const saved = ref<string | null>(null)
const nameField = ref<HTMLInputElement | null>(null)

const languages = computed(() => languageChoices(language.value))

onMounted(() => nameField.value?.focus())

async function save() {
  problem.value = noteProblem({ name: name.value, purpose: purpose.value, language: language.value }, t)
  if (problem.value) return
  busy.value = true
  try {
    const file = await props.session.saveAsTemplate({ name: name.value.trim(), purpose: purpose.value.trim(), language: language.value })
    if (file === false) return // the session has said why
    const result = await downloadBase64(file.filename, file.content_type, file.data)
    if (result.kind === 'cancelled') return
    saved.value = result.kind === 'downloaded' ? '' : result.path
  } catch (e) {
    problem.value = t('The file could not be saved: {reason}', { reason: (e as Error).message })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Modal :title="t('Save as template')" :width="560" @close="emit('close')">
    <form v-if="saved === null" novalidate @submit.prevent="save">
      <div class="row">
        <label class="field grow">{{ t('Name') }}<input ref="nameField" v-model="name" autocomplete="off" :maxlength="MAX_NAME" required ></label>
        <label class="field">
          {{ t('Language') }}
          <select v-model="language">
            <option v-for="choice in languages" :key="choice.tag" :value="choice.tag">{{ choice.name }}</option>
          </select>
        </label>
      </div>
      <label class="field">
        {{ t('What it is for') }}
        <textarea v-model="purpose" rows="3" :maxlength="MAX_PURPOSE" required />
      </label>
      <p class="hint">{{ t('Writes a Claudia export of this presentation without its slides: its layouts and its theme, the styles and the palette.') }}</p>
      <p class="hint">{{ t('Send the file to your server’s administrator, who can add it under Server settings ▸ Templates.') }}</p>
      <p v-if="problem" class="error" role="alert">{{ problem }}</p>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="busy">{{ t('Save file…') }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
      </div>
    </form>
    <template v-else>
      <p v-if="saved">{{ t('Saved as {path}.', { path: saved }) }}</p>
      <p v-else>{{ t('Saved.') }}</p>
      <div class="buttons">
        <button class="btn primary" type="button" @click="emit('close')">{{ t('Done') }}</button>
      </div>
    </template>
  </Modal>
</template>

<style scoped>
.row {
  display: flex;
  gap: 12px;
}
.grow {
  flex: 1 1 auto;
}
.hint {
  margin: 0 0 8px;
  font-size: 12.5px;
  color: var(--muted);
}
.error {
  margin: 0 0 8px;
  font-size: 13px;
  color: color-mix(in srgb, var(--rose) 72%, var(--text));
}
.buttons {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
</style>
