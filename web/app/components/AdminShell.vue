<script setup lang="ts">
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

// The dark sidebar shared by the three server settings pages (E3.11; canvas note s3): "these pages now live on
// the server, not in your Preferences — reached the same way whether it's your own box or someone else's." Same
// components as the client; the dark sidebar and the server's name are the only things that say so.
defineProps<{ label: string; host: string; signedInAs: string; active: 'ai' | 'typeset' | 'access' }>()
const emit = defineEmits<{ navigate: [page: 'ai' | 'typeset' | 'access']; signOut: []; close: [] }>()

const pages: { id: 'ai' | 'typeset' | 'access'; name: string }[] = [
  { id: 'ai', get name() { return t('AI model') } },
  { id: 'typeset', get name() { return t('Typesetting') } },
  { id: 'access', get name() { return t('Access & documents') } },
]
</script>

<template>
  <div class="shell">
    <header class="bar">
      <span>{{ t('Server settings') }}</span>
      <button class="close" type="button" :aria-label="t('Close')" @click="emit('close')">×</button>
    </header>
    <div class="body">
      <nav class="side" :aria-label="t('Server settings pages')">
        <div class="server">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="server-icon">
            <rect x="4" y="4" width="16" height="6" rx="1.5" /><rect x="4" y="14" width="16" height="6" rx="1.5" />
            <circle cx="7.5" cy="7" r="0.6" fill="currentColor" stroke="none" /><circle cx="7.5" cy="17" r="0.6" fill="currentColor" stroke="none" />
          </svg>
          <div class="server-text">
            <div class="server-label">{{ label }}</div>
            <div class="server-host">{{ host }}</div>
            <div class="server-you">{{ t('Signed in as {signedInAs}', { signedInAs }) }}</div>
          </div>
        </div>
        <hr >
        <ul>
          <li v-for="p in pages" :key="p.id">
            <button type="button" :aria-current="p.id === active ? 'page' : undefined" @click="emit('navigate', p.id)">
              <svg v-if="p.id === 'ai'" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3l1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6L12 3z" /></svg>
              <svg v-else-if="p.id === 'typeset'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 5h10l-6.2 7L17 19H7" /></svg>
              <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="15" r="3.2" /><path d="M10.3 12.7L18 5M15.5 7.5l2 2M18 5l2 2" /></svg>
              <span>{{ p.name }}</span>
            </button>
          </li>
        </ul>
        <div class="spacer" />
        <button type="button" class="signout" @click="emit('signOut')">{{ t('Sign out') }}</button>
      </nav>
      <div class="content"><slot /></div>
    </div>
  </div>
</template>

<style scoped>
.shell {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--page);
  color: var(--text);
}
.bar {
  height: 46px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: var(--ink);
  color: var(--paper);
  font: 500 14px var(--font-ui);
}
.close {
  position: absolute;
  right: 10px;
  top: 7px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: color-mix(in srgb, var(--paper) 60%, transparent);
  font-size: 16px;
}
.close:hover {
  background: color-mix(in srgb, var(--paper) 12%, transparent);
}
.body {
  flex: 1 1 auto;
  display: flex;
  min-height: 0;
}
.side {
  width: 220px;
  flex: none;
  padding: 16px 12px;
  background: var(--ink);
  color: var(--paper);
  display: flex;
  flex-direction: column;
}
.server {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 2px 6px 14px;
}
.server-icon {
  flex: none;
  opacity: 0.85;
  margin-top: 1px;
}
.server-text {
  min-width: 0;
}
.server-label {
  font: 600 13.5px var(--font-ui);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.server-host {
  font: 12px var(--font-mono);
  color: color-mix(in srgb, var(--paper) 55%, transparent);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.server-you {
  font: 11.5px var(--font-ui);
  color: color-mix(in srgb, var(--paper) 38%, transparent);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 3px;
}
hr {
  border: none;
  height: 1px;
  background: color-mix(in srgb, var(--paper) 15%, transparent);
  margin: 2px 0 12px;
}
ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.side button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: none;
  background: transparent;
  border-radius: 8px;
  color: color-mix(in srgb, var(--paper) 80%, transparent);
  font: 14px var(--font-ui);
  text-align: left;
}
.side button[aria-current='page'] {
  background: color-mix(in srgb, var(--paper) 12%, transparent);
  color: var(--paper);
  font-weight: 500;
}
.spacer {
  flex: 1 1 auto;
}
.signout {
  padding: 8px 10px;
  border: none;
  background: transparent;
  border-radius: 8px;
  color: color-mix(in srgb, var(--paper) 55%, transparent);
  font: 13px var(--font-ui);
  text-align: left;
}
.signout:hover {
  background: color-mix(in srgb, var(--paper) 10%, transparent);
  color: var(--paper);
}
.content {
  flex: 1 1 auto;
  padding: 28px 36px;
  overflow-y: auto;
  min-width: 0;
}
@media (max-width: 640px) {
  .side {
    width: 180px;
  }
  .content {
    padding: 20px;
  }
}
</style>
