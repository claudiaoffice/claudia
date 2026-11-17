<script setup lang="ts">
// Who may receive a collection's fonts (D1041), as Server settings ▸ Fonts shows it: a sign and a word, never colour
// alone (BITV): a tick for Anywhere, a half-filled circle for This server.
import { mayGoLabel, type MayGo } from '~/lib/admin-fonts'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

defineProps<{ mayGo: MayGo }>()
</script>

<template>
  <span class="badge" :class="mayGo">
    <svg v-if="mayGo === 'anywhere'" width="11" height="11" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 6.5l2.6 2.5L10 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
    <svg v-else width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4.8" fill="none" stroke="currentColor" stroke-width="1.5" /><path d="M6 1.2a4.8 4.8 0 010 9.6z" fill="currentColor" /></svg>
    {{ mayGoLabel(mayGo, t) }}
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 999px;
  padding: 2px 9px;
  font: 500 12px var(--font-ui);
  white-space: nowrap;
}
.anywhere {
  background: color-mix(in srgb, var(--teal) 14%, transparent);
  color: color-mix(in srgb, var(--teal) 72%, var(--text));
}
.this-server {
  background: color-mix(in srgb, var(--iris) 14%, transparent);
  color: color-mix(in srgb, var(--iris) 80%, var(--text));
}
</style>
