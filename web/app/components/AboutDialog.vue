<script setup lang="ts">
// Help ▸ About claudia (D120/D126): new, and web-only — inside a real shell this never even mounts, since
// `help.about` there is `Kind.SHELL` (the window's own native `Adw.AboutDialog`, intercepted before it reaches the
// page at all) and the page isn't drawing its own `MenuBar` in the first place once a shell's `welcome` advertises
// `native-menu` (see `shell.nativeMenu` in the workspace components). This dialog exists for the one case that has
// no shell to ask: a plain browser tab. Nothing here is fetched: the version is the shell-contract version both
// sides already agree on, not a separate build number, since the suite doesn't version itself independently of the
// contract yet.
import { SHELL_CONTRACT_VERSION } from '~/lib/shell-bridge'

defineProps<{ app: 'composes' | 'computes' | 'creates' }>()
const emit = defineEmits<{ close: [] }>()

const BLURB: Record<'composes' | 'computes' | 'creates', string> = {
  composes: 'Write together: text, with everyone in it and the assistant alongside.',
  computes: 'Think with your data: a table, with everyone in it and the assistant alongside.',
  creates: 'Say it on a slide: a presentation, with everyone in it and the assistant alongside.',
}
</script>

<template>
  <Modal title="About claudia" @close="emit('close')">
    <p class="blurb">{{ BLURB[app] }}</p>
    <dl>
      <dt>Part of</dt>
      <dd>claudia, an open-source office suite</dd>
      <dt>Shell contract</dt>
      <dd class="mono">v{{ SHELL_CONTRACT_VERSION }}</dd>
    </dl>
    <p class="hint"><a href="https://github.com/claudiaoffice/claudia" target="_blank" rel="noopener">github.com/claudiaoffice/claudia</a></p>
    <button class="btn primary" type="button" @click="emit('close')">Close</button>
  </Modal>
</template>

<style scoped>
.blurb {
  margin: 0;
  color: var(--text);
}
dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 6px 18px;
  margin: 0;
}
dt {
  font-size: 12px;
  color: var(--app-dark);
  white-space: nowrap;
}
dd {
  margin: 0;
}
.hint {
  margin: 0;
  font-size: 12px;
}
.hint a {
  color: var(--app-dark);
}
button {
  justify-self: start;
}
</style>
