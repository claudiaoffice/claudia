<script setup lang="ts">
import { ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: [] }>()

const name = ref('')
const password = ref('')
const role = ref<'editor' | 'viewer'>('editor')
const added = ref<string[]>([])
const busy = ref(false)
const newKey = ref<string | null>(null)
const isOwner = props.session.state.me.role === 'owner'

async function makeKey() {
  busy.value = true
  newKey.value = await props.session.newRecoveryKey()
  busy.value = false
}

async function add() {
  busy.value = true
  const who = name.value.trim()
  if (await props.session.addUser(who, password.value, role.value)) {
    added.value.push(`${who} (${role.value})`)
    name.value = ''
    password.value = ''
  }
  busy.value = false
}
</script>

<template>
  <RecoveryKeyDialog v-if="newKey" :recovery-key="newKey" :doc="session.state.doc" replacing @done="newKey = null" />
  <Modal v-else title="Share this document" @close="emit('close')">
    <p class="lead">
      Give a colleague a name and a password for <b>{{ session.state.doc }}</b>. They open the document with them, like you did. Tell them the
      password yourself: the server never shows it again.
    </p>
    <form class="form" @submit.prevent="add">
      <label class="field">Name<input v-model="name" autocomplete="off" ></label>
      <label class="field">Password (at least 8 characters, with a capital letter, a small letter and a digit)<input v-model="password" type="text" autocomplete="off" ></label>
      <label class="field">
        May<select v-model="role"><option value="editor">edit</option><option value="viewer">only look</option></select>
      </label>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="busy || !name.trim() || password.length < 8">Add person</button>
        <button class="btn" type="button" @click="emit('close')">Done</button>
      </div>
    </form>
    <ul v-if="added.length" class="added" aria-label="people added just now">
      <li v-for="a in added" :key="a">✓ {{ a }}</li>
    </ul>
    <section v-if="isOwner" class="recovery">
      <h3>Recovery key</h3>
      <p class="lead">
        If somebody forgets their password, the recovery key lets them choose a new one. Making a new key shows it to you once and
        makes the old one stop working.
      </p>
      <div class="buttons"><button class="btn" type="button" :disabled="busy" @click="makeKey">Make a new recovery key</button></div>
    </section>
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
.recovery {
  display: grid;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
h3 {
  margin: 0;
  font: 500 12px/1 var(--font-ui);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
}
.added {
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--teal);
  font-weight: 500;
}
</style>
