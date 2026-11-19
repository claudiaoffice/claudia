<script setup lang="ts">
// File ▸ Download (D110, D1270, E2.12): Claudia's own sealed file, for you to keep. An owner gets the whole file;
// an editor gets it with only her own key slot; a viewer gets only what the content key opens (no history, no chat)
// and her own slot. It opens with the name and password of the person who downloaded it. The file never leaves the
// server unprotected. Your password is asked again because it is also what finds your slot in the file.
// Word, Excel, PowerPoint and OpenDocument files, and (from E2.9) the unencrypted file, are File ▸ Export…
// (`ExportFormatDialog.vue`).
import { computed, ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { downloadBase64 } from '~/lib/download'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: [] }>()

const password = ref('')
const busy = ref(false)
const done = ref(false)
/** Where a desktop window saved it (D501): the person chose it, and sees it again here. */
const savedTo = ref('')
const problem = ref('')

const role = computed(() => props.session.state.me.role)

async function downloadNow() {
  busy.value = true
  problem.value = ''
  try {
    const file = await props.session.downloadClaudia(password.value)
    if (file !== false) {
      const saved = await downloadBase64(file.filename, file.content_type, file.data)
      if (saved.kind !== 'cancelled') {
        savedTo.value = saved.kind === 'downloaded' ? '' : saved.path
        done.value = true
        password.value = ''
      }
    }
  } catch (e) {
    problem.value = t('The file could not be saved: {reason}', { reason: (e as Error).message })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Modal :title="t('Download this document')" @close="emit('close')">
    <TransText v-if="role === 'owner'" tag="p" class="lead" :text="t('This saves {doc} to this computer as a Claudia file: the whole document with its history, its chat and its people, still protected. It opens with the name and password of anybody who belongs to the document.')">
      <template #doc><b>{{ session.state.doc }}</b></template>
    </TransText>
    <TransText v-else-if="role === 'editor'" tag="p" class="lead" :text="t('This saves {doc} to this computer as a Claudia file with its history and its chat, still protected. It opens only with your own name and password.')">
      <template #doc><b>{{ session.state.doc }}</b></template>
    </TransText>
    <TransText v-else tag="p" class="lead" :text="t('This saves the content of {doc} to this computer as a Claudia file, still protected. It has no history and no chat, and it opens only with your own name and password.')">
      <template #doc><b>{{ session.state.doc }}</b></template>
    </TransText>
    <p class="lead">{{ t('For a Word, Excel or PowerPoint file, use File ▸ Export… instead.') }}</p>
    <p v-if="done && savedTo" class="lead" data-testid="download-saved-to">{{ t('Saved as {path}.', { path: savedTo }) }}</p>
    <p v-else-if="done" class="lead" data-testid="download-done">{{ t('Downloaded.') }}</p>
    <p v-if="problem" class="error" role="alert">{{ problem }}</p>
    <form v-if="!done" class="form" @submit.prevent="downloadNow">
      <label class="field">{{ t('Your password, to prepare your copy') }}<PasswordInput v-model="password" autocomplete="current-password" /></label>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="busy || !password">{{ t('Download') }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
      </div>
    </form>
    <div v-else class="buttons">
      <button class="btn" type="button" @click="emit('close')">{{ t('Done') }}</button>
    </div>
  </Modal>
</template>

<style scoped>
.lead {
  margin: 0;
  color: var(--muted);
}
.error {
  margin: 0;
  color: var(--rose);
}
.form {
  display: grid;
  gap: 12px;
}
.buttons {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
</style>
