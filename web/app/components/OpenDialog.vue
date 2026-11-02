<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Link, socketUrl } from '~/lib/protocol'
import { Session } from '~/lib/session'
import { ago } from '~/lib/people'

interface Listed {
  id: string
  app: string
  modified: string
  online: number
}

const emit = defineEmits<{ opened: [session: Session] }>()

const server = new URLSearchParams(location.search).get('server') ?? location.host
const documents = ref<Listed[]>([])
const listError = ref('')
const doc = ref(new URLSearchParams(location.search).get('doc') ?? '')
const user = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

function remembered(key: string): string {
  try {
    return localStorage.getItem(key) ?? ''
  } catch {
    return ''
  }
}
function remember(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* private window: nothing to remember */
  }
}

onMounted(async () => {
  user.value = remembered('claudia.user')
  if (!doc.value) doc.value = remembered('claudia.doc')
  try {
    const answer = await fetch(`${location.protocol}//${server}/api/docs`)
    if (answer.status === 404) listError.value = 'This server does not list its documents. Type the name of yours.'
    else documents.value = (await answer.json()).documents
  } catch {
    listError.value = 'The server cannot be reached.'
  }
})

async function go(create: boolean) {
  error.value = ''
  if (!doc.value.trim() || !user.value.trim() || !password.value) {
    error.value = 'Fill in the document, your name and your password.'
    return
  }
  busy.value = true
  let first = true
  const factory = () => {
    const link = new Link({
      url: socketUrl(doc.value.trim(), { protocol: location.protocol, host: server }),
      user: user.value.trim(),
      password: password.value,
      create: create && first,
    })
    first = false
    return link
  }
  const session = new Session(factory)
  try {
    await session.open()
    if (session.state.sheets.length === 0 && session.state.me.role !== 'viewer') await session.addSheet('Sheet1')
    remember('claudia.user', user.value.trim())
    remember('claudia.doc', doc.value.trim())
    emit('opened', session)
  } catch (e: any) {
    error.value =
      e?.code === 'unauthorized'
        ? create
          ? 'That document exists already — or the name or password is not acceptable. Try Open.'
          : 'The name or password is not right (or there is no such document).'
        : (e?.message ?? 'Could not connect.')
    session.close()
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="open">
    <header>
      <Wordmark />
      <span class="tag"><AppIcon :size="20" /> computes</span>
    </header>
    <section class="card">
      <h1>Think with your data.</h1>
      <p class="sub">Open a table, or start a new one. Everybody you invite works in the same table, and so does the assistant.</p>

      <div class="cols">
        <div class="list">
          <h2>On this server</h2>
          <p v-if="listError" class="hint">{{ listError }}</p>
          <p v-else-if="!documents.length" class="hint">Nothing yet. Create the first document.</p>
          <ul v-else>
            <li v-for="d in documents" :key="d.id">
              <button type="button" :class="{ chosen: d.id === doc }" @click="doc = d.id">
                <span class="name">{{ d.id }}</span>
                <span class="meta">{{ ago(d.modified) }}<template v-if="d.online"> · {{ d.online }} here now</template></span>
              </button>
            </li>
          </ul>
        </div>

        <form @submit.prevent="go(false)">
          <label class="field">Document<input v-model="doc" name="document" autocomplete="off" placeholder="budget-2027" /></label>
          <label class="field">Your name<input v-model="user" name="user" autocomplete="username" placeholder="ann" /></label>
          <label class="field">Password<input v-model="password" name="password" type="password" autocomplete="current-password" /></label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <div class="buttons">
            <button class="btn primary" type="submit" :disabled="busy">Open</button>
            <button class="btn" type="button" :disabled="busy" @click="go(true)">Create document</button>
          </div>
          <p class="hint">A new document belongs to whoever creates it first. The password protects this document only (at least 8 characters, with a capital letter, a small letter and a digit).</p>
        </form>
      </div>
    </section>
  </main>
</template>

<style scoped>
.open {
  min-height: 100%;
  display: grid;
  grid-template-rows: auto 1fr;
  background: linear-gradient(160deg, var(--paper) 55%, var(--mist));
  overflow: auto;
}
header {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 14px 28px;
}
.tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}
.card {
  align-self: start;
  justify-self: center;
  width: min(880px, calc(100% - 32px));
  margin-top: 4vh;
  padding: 36px 40px 32px;
  background: var(--surface);
  border-radius: 18px;
  box-shadow: var(--shadow);
}
h1 {
  font: 400 40px/1.1 var(--font-display);
  margin: 0 0 8px;
}
.sub {
  margin: 0 0 24px;
  color: var(--muted);
  max-width: 52ch;
}
.cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 36px;
}
h2 {
  font: 500 12px/1 var(--font-ui);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 0 0 10px;
}
ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
  max-height: 300px;
  overflow: auto;
}
.list button {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  text-align: left;
  border: 1px solid var(--line);
  background: transparent;
  border-radius: 10px;
  padding: 10px 12px;
}
.list button:hover,
.list button.chosen {
  border-color: var(--app);
  background: var(--app-soft);
}
.name {
  font-weight: 500;
}
.meta {
  color: var(--muted);
  font-size: 12px;
  align-self: center;
}
form {
  display: grid;
  gap: 12px;
  align-content: start;
}
.buttons {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
.hint {
  color: var(--muted);
  font-size: 12px;
  margin: 0;
}
.error {
  color: var(--rose);
  margin: 0;
}
@media (max-width: 736px) {
  .cols {
    grid-template-columns: 1fr;
  }
  .card {
    padding: 24px 20px;
  }
}
</style>
