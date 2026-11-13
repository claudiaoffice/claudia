<script setup lang="ts">
// The "Last changed by … · Apply/Cancel" row every server settings page ends with — identical on all three, so it's
// factored out once rather than copied three times.
import { ago } from '~/lib/people'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

defineProps<{ changed: { by: string; at: string } | null; busy: boolean; error: string }>()
const emit = defineEmits<{ cancel: []; apply: [] }>()
</script>

<template>
  <div class="footer">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="row">
      <div class="changed">
        <TransText v-if="changed" :text="t('Last changed by {by} · {when}', { when: ago(changed.at) })"><template #by><strong>{{ changed.by }}</strong></template></TransText>
      </div>
      <div class="buttons">
        <button class="btn" type="button" :disabled="busy" @click="emit('cancel')">{{ t('Cancel') }}</button>
        <button class="btn primary" type="button" :disabled="busy" @click="emit('apply')">{{ t('Apply') }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.footer {
  margin-top: 8px;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.changed {
  font-size: 12px;
  color: var(--muted);
}
.changed strong {
  color: var(--text);
  font-weight: 500;
}
.buttons {
  display: flex;
  gap: 10px;
  flex: none;
}
.error {
  color: var(--rose);
  margin: 0 0 10px;
}
</style>
