<script setup lang="ts">
// The "Last changed by … · Apply/Cancel" row every server settings page ends with — identical on all three, so it's
// factored out once rather than copied three times.
import { ago } from '~/lib/people'

defineProps<{ changed: { by: string; at: string } | null; busy: boolean; error: string }>()
const emit = defineEmits<{ cancel: []; apply: [] }>()
</script>

<template>
  <div class="footer">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="row">
      <div class="changed">
        <template v-if="changed">Last changed by <strong>{{ changed.by }}</strong> · {{ ago(changed.at) }}</template>
      </div>
      <div class="buttons">
        <button class="btn" type="button" :disabled="busy" @click="emit('cancel')">Cancel</button>
        <button class="btn primary" type="button" :disabled="busy" @click="emit('apply')">Apply</button>
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
