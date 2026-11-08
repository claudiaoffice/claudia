<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watchEffect } from 'vue'
import { Link, socketUrl } from '~/lib/protocol'
import { openSession, type AnySession } from '~/lib/open'
import { Session } from '~/lib/session'
import { ago } from '~/lib/people'
import { currentLocale } from '~/lib/locale'
import { adminUrl, defaultLabel, list as listBookmarks, normalizeServerInput, rename as renameBookmark, upsert as upsertBookmark, type Bookmark } from '~/lib/server-bookmarks'

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

// `server` is a bare host (`host` or `host:port`, as `location.host` gives it); it starts from `?server=` (a dev-only
// escape hatch for pointing this page at a different backend) and otherwise this page's own host. Switching to a
// different bookmarked server is always a full navigation there (below), never an in-page change of this ref to
// another origin — the same "page and socket share one origin" choice the project made for the Linux shell (D115),
// so none of this has to think about a cross-origin fetch.
const server = ref(new URLSearchParams(location.search).get('server') ?? location.host)
const origin = computed(() => `${location.protocol}//${server.value}`)
const bookmarks = ref<Bookmark[]>(listBookmarks())
const renamingOrigin = ref<string | null>(null)
const renameText = ref('')
const connecting = ref(false)
const connectAddress = ref('')
const connectError = ref('')
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

/**
 * What a server says about itself, on landing here or on a fresh mount at a different one (E3.11): its document
 * list, as before, plus the earliest administrator's name if it has one — enough to bookmark it with a sensible
 * label without making anybody open a document first. Both are plain absolute fetches, same as `/api/docs` always
 * was, so pointing this page at another server with `?server=` in dev keeps working exactly as it does today.
 */
async function loadServer() {
  listError.value = ''
  try {
    const answer = await fetch(`${origin.value}/api/docs`)
    if (answer.status === 404) listError.value = 'This server does not list its documents. Type the name of yours.'
    else documents.value = (await answer.json()).documents
  } catch {
    listError.value = 'The server cannot be reached.'
  }
  let administrator: string | null = null
  try {
    const answer = await fetch(`${origin.value}/api/admin/status`)
    if (answer.ok) administrator = (await answer.json()).administrator ?? null
  } catch {
    /* no hint this time — the bare host still makes a fine default label, and it's refreshed on the next visit */
  }
  bookmarks.value = upsertBookmark(origin.value, defaultLabel(origin.value, administrator))
}

onMounted(async () => {
  user.value = remembered('claudia.user')
  if (!doc.value && !props.startFresh) doc.value = remembered('claudia.doc')
  if (props.startFresh) docField.value?.focus()
  await loadServer()
})

function hostOf(bookmarkOrigin: string): string {
  try {
    return new URL(bookmarkOrigin).host
  } catch {
    return bookmarkOrigin
  }
}

/** Go there: a full page navigation to that server's own address, never an in-page fetch to another origin. */
function switchTo(bookmark: Bookmark) {
  if (bookmark.origin !== origin.value) location.href = `${bookmark.origin}/`
}

/** That server's settings pages — reachable from here even for a server nobody has opened a document on yet. */
function manage(bookmark: Bookmark) {
  location.href = adminUrl(bookmark.origin)
}

function startRename(bookmark: Bookmark) {
  renamingOrigin.value = bookmark.origin
  renameText.value = bookmark.label
}

function commitRename() {
  if (renamingOrigin.value) bookmarks.value = renameBookmark(renamingOrigin.value, renameText.value)
  renamingOrigin.value = null
}

function cancelRename() {
  renamingOrigin.value = null
}

function startConnect() {
  connecting.value = true
  connectAddress.value = ''
  connectError.value = ''
}

/** "+ Connect to a server…": a full navigation to whatever address was typed, which lands back in this same dialog
 * at that server's own origin and bookmarks it there (`loadServer`, above) — nothing to connect to in-page. */
function goToTyped() {
  const target = normalizeServerInput(connectAddress.value, location.protocol)
  if (!target) {
    connectError.value = 'Type a server address.'
    return
  }
  location.href = `${target}/`
}

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
      url: socketUrl(doc.value.trim(), { protocol: location.protocol, host: server.value }),
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
    session = await openSession(factory, { host: server.value })
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
      <nav class="servers" aria-label="Server bookmarks">
        <div class="servers-title">Servers</div>
        <ul>
          <li v-for="b in bookmarks" :key="b.origin">
            <input
              v-if="renamingOrigin === b.origin"
              v-model="renameText"
              class="rename"
              :aria-label="`Rename ${b.label}`"
              autofocus
              @keydown.enter="commitRename"
              @keydown.escape="cancelRename"
              @blur="commitRename"
            />
            <template v-else>
              <button type="button" class="server" :aria-current="b.origin === origin ? 'true' : undefined" @click="switchTo(b)">
                <span class="server-dot" :class="{ current: b.origin === origin }" aria-hidden="true" />
                <span class="server-text">
                  <span class="server-name">{{ b.label }}</span>
                  <span class="server-host">{{ hostOf(b.origin) }}</span>
                </span>
              </button>
              <button type="button" class="server-action" title="Rename" :aria-label="`Rename ${b.label}`" @click="startRename(b)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" />
                </svg>
              </button>
              <button type="button" class="server-action" :title="`Manage ${b.label}…`" :aria-label="`Manage ${b.label}…`" @click="manage(b)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="3" />
                  <path
                    d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"
                  />
                </svg>
              </button>
            </template>
          </li>
        </ul>
        <button v-if="!connecting" type="button" class="connect-start" @click="startConnect">+ Connect to a server…</button>
        <form v-else class="connect-form" @submit.prevent="goToTyped">
          <input v-model="connectAddress" aria-label="Server address" placeholder="example.com:8420" autofocus />
          <div class="connect-buttons">
            <button type="submit" class="btn primary small">Go</button>
            <button type="button" class="btn small" @click="connecting = false">Cancel</button>
          </div>
          <p v-if="connectError" class="error">{{ connectError }}</p>
        </form>
      </nav>

      <div class="main">
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
  width: min(1000px, calc(100% - 32px));
  margin-top: 4vh;
  display: flex;
  align-items: stretch;
  background: var(--surface);
  border-radius: 18px;
  box-shadow: var(--shadow);
  overflow: hidden;
}
.main {
  flex: 1 1 auto;
  min-width: 0;
  padding: 36px 40px 32px;
}
.servers {
  width: 240px;
  flex: none;
  padding: 14px 10px;
  background: var(--mist);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
}
.servers-title {
  padding: 4px 8px 8px;
  font: 600 12px var(--font-ui);
  color: var(--muted);
}
.servers ul {
  gap: 3px;
  max-height: 240px;
}
.servers li {
  display: flex;
  align-items: center;
  gap: 1px;
}
.server {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 9px;
  border: none;
  background: transparent;
  border-radius: 9px;
  text-align: left;
  cursor: pointer;
}
.server[aria-current='true'] {
  background: var(--app-soft);
}
.server-dot {
  width: 8px;
  height: 8px;
  flex: none;
  border-radius: 50%;
  background: var(--faint);
}
.server-dot.current {
  background: var(--teal);
}
.server-text {
  min-width: 0;
  flex: 1;
}
.server-name {
  display: block;
  font: 500 13.5px var(--font-ui);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.server-host {
  display: block;
  font: 11.5px var(--font-mono);
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rename {
  width: 100%;
  font: 500 13.5px var(--font-ui);
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--line-field);
  border-radius: 6px;
  padding: 7px 8px;
}
.server-action {
  flex: none;
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  cursor: pointer;
}
.server-action:hover {
  background: var(--faint);
  color: var(--text);
}
.connect-start {
  margin-top: 8px;
  padding: 8px 10px;
  border: 1px dashed var(--line-field);
  border-radius: 9px;
  background: transparent;
  color: var(--muted);
  font: 500 13px var(--font-ui);
  text-align: left;
  cursor: pointer;
}
.connect-form {
  margin-top: 8px;
  display: grid;
  gap: 6px;
}
.connect-form input {
  padding: 7px 9px;
  border: 1px solid var(--line-field);
  border-radius: 7px;
  background: var(--surface);
  color: var(--text);
  font: 13px var(--font-ui);
}
.connect-buttons {
  display: flex;
  gap: 6px;
}
.btn.small {
  padding: 5px 10px;
  font-size: 12.5px;
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
    flex-direction: column;
  }
  .servers {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--line);
  }
  .servers ul {
    max-height: 160px;
  }
  .main {
    padding: 24px 20px;
  }
}
</style>
