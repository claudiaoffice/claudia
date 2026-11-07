<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watchEffect } from 'vue'
import { Link, socketUrl } from '~/lib/protocol'
import { openSession, type AnySession } from '~/lib/open'
import { Session } from '~/lib/session'
import { ago } from '~/lib/people'
import { currentLocale } from '~/lib/locale'

interface Listed {
  id: string
  app: string
  modified: string
  online: number
}

const props = defineProps<{
  /** File ▸ New (D123): land with the document field blank and focused, instead of the one just closed. */
  startFresh?: boolean
}>()
const emit = defineEmits<{ opened: [session: AnySession] }>()

const server = new URLSearchParams(location.search).get('server') ?? location.host
const documents = ref<Listed[]>([])
const listError = ref('')
const doc = ref(new URLSearchParams(location.search).get('doc') ?? '')
const docField = ref<HTMLInputElement | null>(null)
const user = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)
/** The recovery key of a document that was just made, shown before the person goes in (the session waits here). */
const fresh = shallowRef<{ session: AnySession; key: string } | null>(null)
/** "I forgot my password": the form that comes in with the recovery key. */
const recovering = ref(false)
const recoveryKey = ref('')
/** The server serves one app; the documents it lists say which (before that, claudia in general). */
const app = computed(() => documents.value[0]?.app ?? 'claudia')
const words = computed(
  () =>
    ({
      composes: {
        headline: 'Write together.',
        sub: 'Open a text, or start a new one. Everybody you invite writes in the same text, and so does the assistant: it suggests, you decide.',
      },
      creates: {
        headline: 'Say it on a slide.',
        sub: 'Open a presentation, or start a new one. Everybody you invite works on the same slides at the same time.',
      },
    })[app.value] ?? {
      headline: 'Think with your data.',
      sub: 'Open a table, or start a new one. Everybody you invite works in the same table, and so does the assistant.',
    },
)
watchEffect(() => {
  document.documentElement.dataset.app = app.value
})

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
  if (!doc.value && !props.startFresh) doc.value = remembered('claudia.doc')
  if (props.startFresh) docField.value?.focus()
  try {
    const answer = await fetch(`${location.protocol}//${server}/api/docs`)
    if (answer.status === 404) listError.value = 'This server does not list its documents. Type the name of yours.'
    else documents.value = (await answer.json()).documents
  } catch {
    listError.value = 'The server cannot be reached.'
  }
})

/** Show the session at last (a table starts with its first sheet). */
async function enter(session: AnySession) {
  if (session instanceof Session && session.state.sheets.length === 0 && session.state.me.role !== 'viewer') {
    await session.addSheet('Sheet1')
  }
  remember('claudia.user', user.value.trim())
  remember('claudia.doc', doc.value.trim())
  emit('opened', session)
}

function proceed() {
  const waiting = fresh.value
  fresh.value = null
  if (waiting) void enter(waiting.session)
}

/**
 * Connect. `how` decides the first connection only (the one that finds out what the document is): it creates the
 * document, or comes in with the recovery key and the new password. Every later connection (the session's own, and its
 * reconnects) is an ordinary login with what the person typed, which by then is right.
 */
async function go(how: 'open' | 'create' | 'recover') {
  error.value = ''
  const missing = !doc.value.trim() || !user.value.trim() || !password.value || (how === 'recover' && !recoveryKey.value.trim())
  if (missing) {
    error.value =
      how === 'recover'
        ? 'Fill in the document, your name, the recovery key and a new password.'
        : 'Fill in the document, your name and your password.'
    return
  }
  busy.value = true
  let first = true
  const factory = () => {
    const link = new Link({
      url: socketUrl(doc.value.trim(), { protocol: location.protocol, host: server }),
      user: user.value.trim(),
      password: password.value,
      create: how === 'create' && first,
      recoveryKey: how === 'recover' && first ? recoveryKey.value.trim() : undefined,
      locale: currentLocale(),
    })
    first = false
    return link
  }
  let session: AnySession | null = null
  try {
    session = await openSession(factory)
    recoveryKey.value = ''
    const key = session.justCreated ? await session.newRecoveryKey({ quiet: true }) : null
    if (key) fresh.value = { session, key }
    else await enter(session)
  } catch (e: any) {
    error.value =
      e?.code === 'unauthorized'
        ? how === 'create'
          ? 'That document exists already — or the name or password is not acceptable. Try Open.'
          : how === 'recover'
            ? 'That recovery key does not fit this document.'
            : 'The name or password is not right (or there is no such document).'
        : (e?.message ?? 'Could not connect.')
    session?.close()
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="open">
    <header>
      <Wordmark />
      <span class="tag"><AppIcon :size="20" :app="app" /> {{ app }}</span>
    </header>
    <section class="card">
      <h1>{{ words.headline }}</h1>
      <p class="sub">{{ words.sub }}</p>

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

        <form @submit.prevent="go(recovering ? 'recover' : 'open')">
          <label class="field">Document<input ref="docField" v-model="doc" name="document" autocomplete="off" placeholder="budget-2027" /></label>
          <label class="field">Your name<input v-model="user" name="user" autocomplete="username" placeholder="ann" /></label>
          <label v-if="recovering" class="field">
            Recovery key<input v-model="recoveryKey" name="recovery-key" autocomplete="off" spellcheck="false" placeholder="ABCD-EFGH-…" />
          </label>
          <label class="field">
            {{ recovering ? 'New password' : 'Password' }}
            <input v-model="password" name="password" type="password" :autocomplete="recovering ? 'new-password' : 'current-password'" />
          </label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <div class="buttons">
            <template v-if="recovering">
              <button class="btn primary" type="submit" :disabled="busy">Get back in</button>
              <button class="btn" type="button" :disabled="busy" @click="recovering = false">Back</button>
            </template>
            <template v-else>
              <button class="btn primary" type="submit" :disabled="busy">Open</button>
              <button class="btn" type="button" :disabled="busy" @click="go('create')">Create document</button>
            </template>
          </div>
          <p v-if="recovering" class="hint">
            The recovery key was shown to the owner when the document was made (or when they made a new one). With it you choose a new
            password; you keep what you were allowed to do.
          </p>
          <template v-else>
            <p class="hint">A new document belongs to whoever creates it first. The password protects this document only (at least 8 characters, with a capital letter, a small letter and a digit).</p>
            <p class="hint"><button class="link" type="button" @click="recovering = true">I forgot my password</button></p>
          </template>
        </form>
      </div>
    </section>
    <RecoveryKeyDialog v-if="fresh" :recovery-key="fresh.key" :doc="doc.trim()" @done="proceed" />
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
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
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
.link {
  border: 0;
  padding: 0;
  background: none;
  color: var(--app-text); /* --app as literal text fails contrast in dark mode — the owner's 2026-11-06 report */
  font: inherit;
  text-decoration: underline;
  cursor: pointer;
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
