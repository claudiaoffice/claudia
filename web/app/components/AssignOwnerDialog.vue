<script setup lang="ts">
// File ▸ Manage ▸ Assign new owner… (D141). A role lives inside its own password-sealed slot (D102), so handing
// one over is a propose/accept pair: we prove it is us with our own password now, and the person we pick proves it
// is them with theirs when they accept (elsewhere, the next time they open this menu and see the offer — there is
// no separate "accept" screen yet; see the decision log).
import { onMounted, ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: [] }>()

const editors = ref<string[]>([])
const loaded = ref(false)
const chosen = ref('')
const password = ref('')
const busy = ref(false)
const proposed = ref<string | null>(null)

onMounted(async () => {
  const roster = await props.session.roster()
  if (roster !== false) editors.value = roster.filter((p) => p.role === 'editor').map((p) => p.user)
  loaded.value = true
})

async function propose() {
  busy.value = true
  if (await props.session.proposeOwner(chosen.value, password.value)) proposed.value = chosen.value
  busy.value = false
}
</script>

<template>
  <Modal :title="t('Assign a new owner')" @close="emit('close')">
    <TransText v-if="proposed" tag="p" class="lead" :text="t('{who} has been asked to take over {doc}. Until they accept, you are still the owner. You will become an editor the moment they do.')">
      <template #who><b>{{ proposed }}</b></template>
      <template #doc><b>{{ session.state.doc }}</b></template>
    </TransText>
    <template v-else>
      <TransText tag="p" class="lead" :text="t('Hand {doc} over to somebody who already edits it. You will become an editor; they become the owner once they accept — confirm it is you with your own password.')">
        <template #doc><b>{{ session.state.doc }}</b></template>
      </TransText>
      <form v-if="loaded" class="form" @submit.prevent="propose">
        <label v-if="editors.length" class="field"
          >{{ t('New owner') }}
          <select v-model="chosen">
            <option value="" disabled>{{ t('Choose somebody…') }}</option>
            <option v-for="name in editors" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>
        <p v-else class="lead">{{ t('Nobody edits this document yet. Make somebody an editor first (File ▸ Manage ▸ Share…).') }}</p>
        <label v-if="editors.length" class="field">{{ t('Your password') }}<input v-model="password" type="password" autocomplete="current-password" ></label>
        <div class="buttons">
          <button v-if="editors.length" class="btn primary" type="submit" :disabled="busy || !chosen || !password">{{ t('Ask them to take over') }}</button>
          <button class="btn" type="button" @click="emit('close')">{{ editors.length ? t('Cancel') : t('Close') }}</button>
        </div>
      </form>
    </template>
    <div v-if="proposed" class="buttons">
      <button class="btn primary" type="button" @click="emit('close')">{{ t('Done') }}</button>
    </div>
  </Modal>
</template>

<style scoped>
.lead {
  margin: 0;
  color: var(--muted);
}
.form {
  display: grid;
  gap: 12px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
