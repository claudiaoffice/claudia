<script setup lang="ts">
// Preferences ▸ AI… (E7.11, D264): the owners decide whether Claude may be sent this document's content when somebody
// asks @ai. Off by default. Everybody sees the state and who answers now; only an owner has the checkbox.
import { computed, ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { badge, consentDialog } from '~/lib/ai-provider'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: [] }>()

const view = computed(() => props.session.state.consent)
const dialog = computed(() => (view.value ? consentDialog(view.value, props.session.state.me.role) : null))
const allowed = ref(view.value?.allowed ?? false)
const busy = ref(false)

async function save() {
  if (dialog.value?.mode !== 'owner') return emit('close')
  busy.value = true
  // Nothing to send when nothing changed: the history would get a line for a decision nobody made.
  const done = allowed.value === view.value?.allowed || (await props.session.setAiConsent(allowed.value))
  busy.value = false
  if (done) emit('close')
}
</script>

<template>
  <Modal :title="t('AI in this document')" :width="480" @close="emit('close')">
    <p v-if="!view || !dialog" class="lead">{{ t('This server does not keep the owner’s choice about Claude.') }}</p>
    <form v-else class="form" @submit.prevent="save">
      <p v-if="view.answering" class="now" data-testid="ai-answering">
        {{ t('Answering @ai in this document now') }}
        <span class="badge" :class="{ remote: view.answering.remote }">{{ badge(view.answering) }}</span>
      </p>

      <p v-if="dialog.noRemoteNote" class="lead" data-testid="ai-no-remote">
        {{ t('This server has no remote AI, so nothing in this document leaves it. An administrator can add Claude in the server settings. Then the owner can allow it here.') }}
      </p>

      <template v-if="dialog.mode !== 'no-remote'">
        <label class="check">
          <input v-model="allowed" type="checkbox" :disabled="dialog.mode !== 'owner'">
          <span>{{ t('Allow Claude to answer @ai in this document') }}</span>
        </label>
        <p class="lead">{{ dialog.mode === 'owner' ? t('Off by default. Only the owner can change it.') : dialog.ownerLine }}</p>

        <div class="sent">
          <p>{{ t('If you allow it, Anthropic is sent:') }}</p>
          <ul>
            <li>{{ t('the question, and the earlier chat between the person who asks and the ai') }}</li>
            <li>{{ t('the parts of this document the ai looks at to answer her') }}</li>
          </ul>
          <p class="lead">{{ t('Documents are encrypted on this server. Claude reads what it is shown in plain text.') }}</p>
        </div>

        <p v-if="dialog.allowedLine" class="lead" data-testid="ai-decided">{{ dialog.allowedLine }}</p>
        <p v-if="dialog.mode === 'owner'" class="lead">{{ t('Switching it off stops a question that is running before its next step.') }}</p>
      </template>

      <div class="buttons">
        <template v-if="dialog.mode === 'owner'">
          <button class="btn primary" type="submit" :disabled="busy">{{ t('Save') }}</button>
          <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
          <span class="lead keys">{{ t('Enter saves · Esc cancels') }}</span>
        </template>
        <button v-else class="btn primary" type="submit">{{ t('Close') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.form {
  display: grid;
  gap: 12px;
}
.lead {
  margin: 0;
  color: var(--muted);
}
.now {
  margin: 0;
  display: flex;
  gap: 8px;
  align-items: center;
}
.badge {
  padding: 1px 8px;
  border: 1px solid var(--border, currentColor);
  border-radius: 10px;
  font-size: 0.85em;
}
.badge.remote {
  font-weight: 600;
}
.check {
  display: flex;
  gap: 8px;
  align-items: center;
}
.sent p,
.sent ul {
  margin: 0 0 6px;
}
.buttons {
  display: flex;
  gap: 10px;
  align-items: center;
}
.keys {
  margin-left: auto;
  font-size: 0.85em;
}
</style>
