<script setup lang="ts">
// "Back where I was" (D1312): after a tag in the chat took the view somewhere else, this chip floats over the view and
// takes the person back. It is not part of the chat panel, so it is there with History & Chat folded away. It stays
// until it is used, the person types or clicks into the text, or the next tag takes its place; Esc lets go of it.
// For a screen reader it is a status region (BITV 4.1.3): it appears without taking the focus, and View ▸ Back where
// I was (Ctrl+Shift+B) is the keyboard's way to the same.
import { onBeforeUnmount, onMounted } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()
const props = defineProps<{ session: BaseSession }>()

function onEscape(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.session.state.wayBack && !event.defaultPrevented) props.session.clearBack()
}
onMounted(() => window.addEventListener('keydown', onEscape))
onBeforeUnmount(() => window.removeEventListener('keydown', onEscape))
</script>

<template>
  <div class="backChip" role="status" data-testid="back-chip">
    <button v-if="session.state.wayBack" type="button" :title="t('Esc lets go of this')" @click="session.goBack()">{{ t('← Back where I was') }}</button>
  </div>
</template>

<style scoped>
.backChip {
  position: fixed;
  bottom: 18px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 20;
}
.backChip button {
  border: 1px solid rgb(242 160 87 / 55%);
  border-radius: 999px;
  background: #2a2342;
  color: var(--apricot);
  font: 500 13px var(--font-ui);
  padding: 6px 14px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgb(0 0 0 / 30%);
}
.backChip button:focus-visible {
  outline: 2px solid var(--apricot);
  outline-offset: 2px;
}
</style>
