<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  /** The key as the server wrote it: 13 groups of 4 letters and digits. */
  recoveryKey: string
  doc: string
  /** A key that was just made for a document that was just made says so; a replacement says what stopped working. */
  replacing?: boolean
}>()
const emit = defineEmits<{ done: [] }>()

const stored = ref(false)
const copied = ref<'' | 'yes' | 'no'>('')

// D128 made Esc always close a dialog, "locked" ones included — right for Share… or Save new checkpoint, wrong here:
// there is no legitimate way to leave without the checkbox below, since losing the only copy of a recovery key is
// not an Esc-sized mistake to let through. `modal.reopen()` is this one dialog's deliberate, narrow exception.
const modal = ref<{ reopen: () => void } | null>(null)
function keepOpen() {
  if (!stored.value) modal.value?.reopen()
}

async function copy() {
  try {
    await navigator.clipboard.writeText(props.recoveryKey)
    copied.value = 'yes'
  } catch {
    copied.value = 'no' // no clipboard here (an unsecured page, say): the key is shown to be copied by hand
  }
}
</script>

<template>
  <Modal ref="modal" :title="t('Your recovery key')" :width="520" locked @close="keepOpen">
    <p class="lead">
      <TransText :text="t('This is the only way back into {doc} for somebody who has forgotten their password.')"><template #doc><b>{{ doc }}</b></template></TransText>
      <template v-if="replacing">{{ t('The key you had before no longer works.') }}</template>
      <TransText :text="t('The server does not keep it and will {never}: write it down or put it in your password manager, and keep it away from the document.')"><template #never><b>{{ t('never show it again') }}</b></template></TransText>
    </p>
    <div class="key" data-testid="recovery-key" :aria-label="t('recovery key')">
      <code v-for="(group, i) in recoveryKey.split('-')" :key="i">{{ group }}</code>
    </div>
    <div class="row">
      <button class="btn" type="button" @click="copy">{{ t('Copy') }}</button>
      <span v-if="copied === 'yes'" class="ok" role="status">{{ t('Copied.') }}</span>
      <span v-else-if="copied === 'no'" class="hint" role="status">{{ t('Your browser would not copy it: select the key and copy it yourself.') }}</span>
    </div>
    <label class="confirm"><input v-model="stored" type="checkbox" > {{ t('I have stored the recovery key somewhere safe.') }}</label>
    <div class="buttons">
      <button class="btn primary" type="button" :disabled="!stored" @click="emit('done')">{{ t('Continue') }}</button>
    </div>
  </Modal>
</template>

<style scoped>
.lead {
  margin: 0;
  color: var(--muted);
}
.key {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px 10px;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode; the key must not go unreadable there */
  user-select: all;
}
code {
  font: 500 15px/1.3 var(--font-mono);
  letter-spacing: 0.04em;
}
.row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ok {
  color: var(--teal);
  font-weight: 500;
}
.hint {
  color: var(--muted);
  font-size: 12px;
}
.confirm {
  display: flex;
  gap: 8px;
  align-items: center;
}
.buttons {
  display: flex;
  justify-content: flex-end;
}
@media (max-width: 520px) {
  .key {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
