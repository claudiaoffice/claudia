<script setup lang="ts">
import { computed } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { colorOf, initial, inkOn } from '~/lib/people'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ session: BaseSession; panelOpen: boolean }>()
defineEmits<{ togglePanel: [] }>()

const state = props.session.state
const everybody = computed(() => [
  { user: state.me.user, color: state.me.color, me: true },
  ...state.people.map((p) => ({ user: p.user, color: colorOf(state, p.user), me: false })),
])
</script>

<template>
  <header class="bar">
    <div class="brand">
      <Wordmark />
      <span class="app"><AppIcon :size="22" :app="state.app" /> {{ state.app || 'claudia' }}</span>
    </div>
    <h1 class="doc" :title="t('document {doc}', { doc: state.doc })">{{ state.doc }}</h1>
    <div class="right">
      <ul class="people" :aria-label="t('people in this document')">
        <li
          v-for="p in everybody"
          :key="p.user"
          :title="p.me ? t('{user} (you)', { user: p.user }) : p.user"
          :style="{ background: p.color, color: inkOn(p.color) }"
          :class="{ ai: p.user.toLowerCase() === 'ai' }"
        >
          {{ p.user.toLowerCase() === 'ai' ? 'ai' : initial(p.user) }}
        </li>
      </ul>
      <ConnectionIndicator :session="session" />
      <button class="btn panel" type="button" :aria-pressed="panelOpen" @click="$emit('togglePanel')">{{ t('History & chat') }}</button>
    </div>
  </header>
</template>

<style scoped>
.bar {
  display: flex;
  align-items: center;
  gap: 24px;
  height: 52px;
  padding: 0 16px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
}
.app {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-weight: 500;
  padding-left: 14px;
  border-left: 1px solid var(--line);
}
.doc {
  font: 500 19px/1 var(--font-display);
  margin: 0;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.right {
  display: flex;
  align-items: center;
  gap: 14px;
}
.people {
  display: flex;
  list-style: none;
  margin: 0;
  padding: 0;
}
.people li {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 500;
  border: 2px solid var(--surface);
  margin-left: -6px;
}
.people li:first-child {
  margin-left: 0;
}
.panel[aria-pressed='true'] {
  background: var(--mist);
  border-color: transparent;
  color: var(--ink); /* `--mist` stays light in dark mode; don't let the text follow `--text` into Paper */
}
@media (max-width: 736px) {
  .app {
    display: none;
  }
  .bar {
    gap: 10px;
    padding: 0 10px;
  }
  .right {
    gap: 8px;
  }
  .doc {
    font-size: 17px;
  }
  .panel {
    padding: 0 10px;
    white-space: nowrap;
  }
}
@media (max-width: 440px) {
  .panel {
    font-size: 13px;
  }
}
</style>
