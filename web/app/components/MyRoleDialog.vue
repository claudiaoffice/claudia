<script setup lang="ts">
// File ▸ Manage ▸ My Role… (the workbook, UX-95): the one place for what a person does about their own role. It says
// what that role is and leads to the three steps, each its own dialog as before (D141): an owner hands the document
// over, somebody who was asked accepts it, and anyone leaves. The server says no where a step does not apply to you
// (an editor nobody asked to take over, the only owner leaving), so no choice is hidden on a guess.
import { computed } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { useI18n } from '~/lib/i18n'
import type { FrameDialog } from '~/lib/menus/window-handlers'

const { t } = useI18n()

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: []; choose: [step: FrameDialog] }>()

const owner = computed(() => props.session.state.me.role === 'owner')
const role = computed(() => {
  const now = props.session.state.me.role
  if (now === 'owner') return t('You are an owner of {doc}.')
  if (now === 'viewer') return t('You may only look at {doc}.')
  return t('You edit {doc}.')
})
</script>

<template>
  <Modal :title="t('My Role')" @close="emit('close')">
    <div class="steps" data-testid="my-role">
      <TransText tag="p" class="lead" :text="role">
        <template #doc><b>{{ session.state.doc }}</b></template>
      </TransText>
      <div v-if="owner" class="step">
        <button class="btn" type="button" @click="emit('choose', 'assign-owner')">{{ t('Hand Over…') }}</button>
        <p class="hint">{{ t('Make somebody who edits it the owner; you become an editor once they accept.') }}</p>
      </div>
      <div v-else class="step">
        <button class="btn" type="button" @click="emit('choose', 'accept-owner')">{{ t('Accept Ownership…') }}</button>
        <p class="hint">{{ t('If an owner asked you to take the document over, accept it here.') }}</p>
      </div>
      <div class="step">
        <button class="btn" type="button" @click="emit('choose', 'leave')">{{ t('Leave the Document…') }}</button>
        <p class="hint">{{ t('You can no longer open it, unless somebody adds you again. The only owner cannot leave.') }}</p>
      </div>
      <div class="buttons">
        <button class="btn primary" type="button" @click="emit('close')">{{ t('Close') }}</button>
      </div>
    </div>
  </Modal>
</template>

<style scoped>
.steps {
  display: grid;
  gap: 14px;
}
.lead {
  margin: 0;
}
.step {
  display: grid;
  grid-template-columns: max-content 1fr;
  align-items: center;
  gap: 12px;
}
.hint {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
