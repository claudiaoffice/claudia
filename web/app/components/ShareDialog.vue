<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { useI18n } from '~/lib/i18n'
import { roleName } from '~/lib/people'

const { t } = useI18n()

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
    await loadPeople()
  }
  busy.value = false
}

// People in this document, with a role each and a way out (E2.3, D1263). Lowering a role and removing somebody renew
// keys, so they ask first and say what that protects and what it does not.
type Who = { user: string; role: string }
type Pending = { kind: 'lower' | 'remove'; person: Who }
const people = ref<Who[]>([])
const pending = ref<Pending | null>(null)
const renewing = ref(false)

async function loadPeople() {
  if (!isOwner) return
  const roster = await props.session.roster()
  if (roster !== false) people.value = roster
}

onMounted(loadPeople)

async function pick(person: Who, event: Event) {
  const target = (event.target as HTMLSelectElement).value as 'editor' | 'viewer'
  if (target === person.role) return
  if (target === 'viewer') {
    ;(event.target as HTMLSelectElement).value = person.role // not changed until it is confirmed
    pending.value = { kind: 'lower', person }
    return
  }
  await props.session.changeRole(person.user, target)
  await loadPeople()
}

async function confirm() {
  const current = pending.value
  if (!current) return
  renewing.value = true
  if (current.kind === 'lower') await props.session.changeRole(current.person.user, 'viewer')
  else await props.session.removePerson(current.person.user)
  renewing.value = false
  pending.value = null
  await loadPeople()
}
</script>

<template>
  <RecoveryKeyDialog v-if="newKey" :recovery-key="newKey" :doc="session.state.doc" replacing @done="newKey = null" />
  <Modal v-else-if="pending" :title="pending.kind === 'lower' ? t('Change {user} to “only look”?', { user: pending.person.user }) : t('Remove {user} from “{doc}”?', { user: pending.person.user, doc: session.state.doc })" @close="renewing || (pending = null)">
    <template v-if="renewing">
      <p class="lead" role="status">{{ t('Renewing the keys…') }}</p>
      <p class="lead">{{ t('{doc} can be read and edited as usual while this runs. A long document takes longer: about as long as writing the file once.', { doc: session.state.doc }) }}</p>
    </template>
    <template v-else-if="pending.kind === 'lower'">
      <p>{{ t('From now on {user} cannot read what is written to the history or the chat. {user} keeps what has already been seen and any copy that was saved. The document’s keys are renewed; for this document that takes about a second.', { user: pending.person.user }) }}</p>
      <p class="lead">{{ t('Why: the old keys still open what was written before; the new ones protect what is written from now on.') }}</p>
      <div class="buttons">
        <button class="btn" type="button" @click="pending = null">{{ t('Cancel') }}</button>
        <button class="btn primary" type="button" @click="confirm">{{ t('Change to only look') }}</button>
      </div>
    </template>
    <template v-else>
      <p>{{ t('{user} will no longer be able to open this document or read anything written after now.', { user: pending.person.user }) }}</p>
      <p>{{ t('{user} keeps what has already been seen and any copy of the file that was saved.', { user: pending.person.user }) }}</p>
      <p>{{ t('Any private notes of this person are deleted.') }}</p>
      <p class="lead">{{ t('The document’s keys are renewed. This takes a moment, and everybody who is here stays connected.') }}</p>
      <div class="buttons">
        <button class="btn" type="button" @click="pending = null">{{ t('Cancel') }}</button>
        <button class="btn primary" type="button" @click="confirm">{{ t('Remove {user}', { user: pending.person.user }) }}</button>
      </div>
    </template>
  </Modal>
  <Modal v-else :title="t('Share this document')" @close="emit('close')">
    <section v-if="isOwner && people.length" class="people">
      <h3>{{ t('People in this document') }}</h3>
      <ul class="roster">
        <li v-for="p in people" :key="p.user">
          <span class="who">{{ p.user }}<small v-if="p.user === session.state.me.user"> · {{ t('you') }}</small></span>
          <span v-if="p.role === 'owner'" class="role">{{ roleName(p.role) }}</span>
          <template v-else>
            <select :value="p.role" :aria-label="t('What {user} may do', { user: p.user })" @change="pick(p, $event)">
              <option value="editor">{{ t('edit') }}</option>
              <option value="viewer">{{ t('only look') }}</option>
            </select>
            <button class="btn" type="button" @click="pending = { kind: 'remove', person: p }">{{ t('Remove') }}</button>
          </template>
        </li>
      </ul>
    </section>
    <TransText tag="p" class="lead" :text="t('Give a colleague a name and a password for {doc}. They open the document with them, like you did. Tell them the password yourself: the server never shows it again.')">
      <template #doc><b>{{ session.state.doc }}</b></template>
    </TransText>
    <form class="form" @submit.prevent="add">
      <label class="field">{{ t('Name') }}<input v-model="name" autocomplete="off" ></label>
      <label class="field">{{ t('Password (at least 8 characters, with a capital letter, a small letter and a digit)') }}<PasswordInput v-model="password" name="share-password" autocomplete="off" /></label>
      <label class="field">
        {{ t('May') }}<select v-model="role"><option value="editor">{{ t('edit') }}</option><option value="viewer">{{ t('only look') }}</option></select>
      </label>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="busy || !name.trim() || password.length < 8">{{ t('Add person') }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Done') }}</button>
      </div>
    </form>
    <ul v-if="added.length" class="added" :aria-label="t('people added just now')">
      <li v-for="a in added" :key="a">✓ {{ a }}</li>
    </ul>
    <section v-if="isOwner" class="recovery">
      <h3>{{ t('Recovery key') }}</h3>
      <p class="lead">
        {{ t('If somebody forgets their password, the recovery key lets them choose a new one. Making a new key shows it to you once and makes the old one stop working.') }}
      </p>
      <div class="buttons"><button class="btn" type="button" :disabled="busy" @click="makeKey">{{ t('Make a new recovery key') }}</button></div>
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
.roster {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.roster li {
  display: flex;
  align-items: center;
  gap: 10px;
}
.who {
  flex: 1;
}
.role {
  color: var(--muted);
}
.people {
  display: grid;
  gap: 8px;
}
.added {
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--teal);
  font-weight: 500;
}
</style>
