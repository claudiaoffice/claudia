<script setup lang="ts">
// Help ▸ About claudia (D120/D126), rebuilt 2026-11-06 to match the Linux shell's own About dialog exactly (D28,
// the owner's report that the two had drifted apart): the app's own logo, its name, then the same three outbound
// links the shell's `about_links()` gives it — Website, Report an Issue, Legal — in the same order, nothing added.
//
// Shown in a plain browser tab and in the Windows and macOS clients (Neutralino), which have no About dialog of their
// own: there the native menu's Help ▸ About is sent to the page, which opens this (the document's menus, and the start
// page, CODE-94). Only the Linux shell has a native dialog of its own, and never sends the action to the page. The
// version shown is the shell-contract version both sides already agree on, not a separate build number, since the suite
// doesn't version itself independently of the contract yet (the Linux shell's own `__version__` is that build
// number, and has no web equivalent to show here).
import { APP_NAME, SHELL_CONTRACT_VERSION } from '~/lib/shell-bridge'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

defineProps<{ app: 'composes' | 'computes' | 'creates' }>()
const emit = defineEmits<{ close: [] }>()

const TITLE = APP_NAME

// Kept in step with `window.py`'s `about_links()` by hand: the two shells have no manifest in common for this, so
// whichever one of us changes this list has to change the other too.
const LINKS: { label: string; href: string }[] = [
  { get label() { return t('Website') }, href: 'https://www.claudia-office.de' },
  { get label() { return t('Report an Issue') }, href: 'https://github.com/claudiaoffice/claudia/issues' },
  { get label() { return t('Legal') }, href: 'https://github.com/claudiaoffice/claudia/blob/main/LICENSE' },
]
</script>

<template>
  <Modal :title="t('About claudia')" @close="emit('close')">
    <div class="about">
      <AppIcon :size="64" :app="app" />
      <h3>{{ TITLE[app] }}</h3>
      <p class="version mono">{{ t('Shell contract v{SHELL_CONTRACT_VERSION}', { SHELL_CONTRACT_VERSION }) }}</p>
      <div class="links">
        <a v-for="link in LINKS" :key="link.label" class="btn" :href="link.href" target="_blank" rel="noopener">{{ link.label }}</a>
      </div>
      <button class="btn primary" type="button" @click="emit('close')">{{ t('Close') }}</button>
    </div>
  </Modal>
</template>

<style scoped>
.about {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
  padding-top: 4px;
}
h3 {
  margin: 10px 0 0;
  font: 500 17px var(--font-ui);
  color: var(--text);
}
.version {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--muted);
}
.links {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-self: stretch;
}
.links .btn {
  text-align: center;
  text-decoration: none;
  color: var(--text);
}
.about > .btn.primary {
  margin-top: 8px;
  align-self: center;
}
</style>
