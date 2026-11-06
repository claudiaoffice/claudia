<script setup lang="ts">
// File ▸ Manage ▸ Assign new owner… (D135). A role lives inside its own password-sealed slot (D102), so handing
// one over is a propose/accept pair: we prove it is us with our own password now, and the person we pick proves it
// is them with theirs when they accept (elsewhere, the next time they open this menu and see the offer — there is
// no separate "accept" screen yet; see the decision log).
import { onMounted, ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'

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
  <Modal title="Assign a new owner" @close="emit('close')">
    <p v-if="proposed" class="lead">
      <b>{{ proposed }}</b> has been asked to take over <b>{{ session.state.doc }}</b>. Until they accept, you are still the owner. You will become an
      editor the moment they do.
    </p>
    <template v-else>
      <p class="lead">
        Hand <b>{{ session.state.doc }}</b> over to somebody who already edits it. You will become an editor; they become the owner once they accept —
        confirm it is you with your own password.
      </p>
      <form v-if="loaded" class="form" @submit.prevent="propose">
        <label v-if="editors.length" class="field"
          >New owner
          <select v-model="chosen">
            <option value="" disabled>Choose somebody…</option>
            <option v-for="name in editors" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>
        <p v-else class="lead">Nobody edits this document yet. Make somebody an editor first (File ▸ Manage ▸ Share…).</p>
        <label v-if="editors.length" class="field">Your password<input v-model="password" type="password" autocomplete="current-password" /></label>
        <div class="buttons">
          <button v-if="editors.length" class="btn primary" type="submit" :disabled="busy || !chosen || !password">Ask them to take over</button>
          <button class="btn" type="button" @click="emit('close')">{{ editors.length ? 'Cancel' : 'Close' }}</button>
        </div>
      </form>
    </template>
    <div v-if="proposed" class="buttons">
      <button class="btn primary" type="button" @click="emit('close')">Done</button>
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
