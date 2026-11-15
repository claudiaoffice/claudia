<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch, watchEffect } from 'vue'
import { Link, socketUrl } from '~/lib/protocol'
import { appOfFileName, appOfServer, fetchDocsListing, filterByTag, filterListed, openSession, openableFor, placeUpload, saveDetails, sendFile, tagCounts, type AnySession, type Listed, type Upload, type Uploaded } from '~/lib/open'
import type { ImportPhase } from '~/lib/import-progress'
import { createCollection, deleteCollection, entriesOf, forgetMine, keyOf, listCollections, listMine, nextShown, parseKey, rememberOpened, setInCollection, stillShown, type MineEntry } from '~/lib/mine'
import { holdPresence } from '~/lib/presence'
import { chooseLocalFile } from '~/lib/local-files'
import { ago } from '~/lib/people'
import { currentLocale } from '~/lib/locale'
import { adminUrl, defaultLabel, list as listBookmarks, normalizeServerInput, rename as renameBookmark, upsert as upsertBookmark, withBookmark, withRenamed, type Bookmark } from '~/lib/server-bookmarks'
import { createShellBridge, detectHandler, detectParentSink, isApp, type ShellBridge } from '~/lib/shell-bridge'
import { LANGUAGES, useI18n } from '~/lib/i18n'
import { useTheme } from '~/lib/theme'
import Modal from './Modal.vue'

const { t, locale, choose: chooseLanguage } = useI18n()
const { dark, toggle: toggleDark } = useTheme()

const props = defineProps<{
  /** File ▸ New (D123): land with the document field blank and focused, instead of the one just closed. */
  startFresh?: boolean
  /** File ▸ Open… (sheet 10, B1): shown in a dialog over a document, which it replaces once another is open. */
  modal?: boolean
  /** File ▸ Open a File…: ask for a file at once. */
  pickFile?: boolean
  /** In the dialog: the document's own conversation with the shell. The dialog borrows it (the shell's server list,
   * the window's app); a second bridge would take the shell's messages away from the document for good. */
  shellBridge?: (ShellBridge & { detach: () => void }) | null
}>()
const emit = defineEmits<{ opened: [session: AnySession]; close: [] }>()

// `server` is a bare host (`host` or `host:port`, as `location.host` gives it); it starts from `?server=` (a dev-only
// escape hatch for pointing this page at a different backend) and otherwise this page's own host. Switching to a
// different bookmarked server is always a full navigation there (below), never an in-page change of this ref to
// another origin — the same "page and socket share one origin" choice the project made for the Linux shell (D115),
// so none of this has to think about a cross-origin fetch.
const server = ref(new URLSearchParams(location.search).get('server') ?? location.host)
const origin = computed(() => `${location.protocol}//${server.value}`)
// Where the servers come from. In a plain browser they are this browser's own bookmarks (`localStorage`, per origin).
// In a Claudia desktop shell the shell keeps them — one list per app, across servers, with "This computer" first when
// the shell started a server — and connecting to one is the shell's job: it checks the server, then shows it in this
// same window. (A page that navigated there itself would be handed to the person's browser: the shell never lets its
// view leave the server it showed.)
const stored = ref<Bookmark[]>(listBookmarks())
const shell = ref<(ShellBridge & { detach: () => void }) | null>(null)
const inShell = (detectHandler() ?? detectParentSink()) !== null // a native shell: WebKit's handler, or a Neutralino parent
const viaShell = computed(() => shell.value?.hasServerList === true)
const bookmarks = computed<Bookmark[]>(() => (viaShell.value ? (shell.value?.servers ?? []) : stored.value))
/** The label to give the server this page is on once it is clear where the list lives (see `settle`). */
let pendingLabel = ''
const connectPending = ref(false)
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
/** What `/api/docs` said this server serves, before any document has been opened or even made. */
const serverApp = ref('')
/** The apps this server hosts (D430): one for a server of one app, three for the one server of the suite. */
const apps = ref<string[]>([])
const isSuite = computed(() => apps.value.length > 1)
/** The app of the document chosen from a list (its address names the app, D431); '' for a name typed by hand. */
const docApp = ref('')
/** The kind of a new document: asked every time on a server of several apps (sheet 10). */
const newApp = ref('')
const query = ref('')
const appFilter = ref(new URLSearchParams(location.search).get('app') ?? '')
const searchField = ref<HTMLInputElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
/** The first control of "Or start a new one", for File ▸ New in the native menu. */
const newStart = ref<HTMLButtonElement | null>(null)
/** Mine and the collections (D443): kept in this browser, never on a server. */
const mine = ref<MineEntry[]>(listMine())
const collections = ref(listCollections())
const shownCollection = ref<string | null>(null)
const newCollection = ref<string | null>(null)
/** A file from the computer, held by the server until it becomes a document (D440); while it is still on its way,
 * what is known from its name. */
const incoming = shallowRef<Uploaded | null>(null)
/** Where that file is: sending, waiting for Open, reading, opening (the one bar of sheet 11). */
const importPhase = ref<ImportPhase>('sending')
const importSent = ref(0)
let upload: Upload | null = null
const importError = ref('')
const notice = ref('')
const dragging = ref(false)
const APP_WORDS: Record<string, () => string> = { computes: () => t('Table'), composes: () => t('Text'), creates: () => t('Slides') }
/** A file of another app, refused by a desktop window (D444). */
const refusal = ref('')
/** The app of the desktop window this page is in (D444): its documents only, its files only. `null` in a browser tab. */
const windowApp = computed(() => shell.value?.windowApp ?? null)
/** Every app with the filter (a browser tab on a server of several apps), or one app. */
const showsAll = computed(() => isSuite.value && !windowApp.value)
/** The app the lists are narrowed to: the window's, else the filter's ('' for all). */
const shownApp = computed(() => windowApp.value ?? appFilter.value)
/** The server serves one app and says so; a listed document is the fallback (see `appOfServer`). */
const app = computed(() =>
  windowApp.value ??
  (isSuite.value ? docApp.value || appFilter.value || 'claudia' : appOfServer({ app: serverApp.value, documents: documents.value })),
)
/** The place shown, in the sidebar's words. */
const placeLabel = computed(() => bookmarks.value.find((b) => b.origin === origin.value)?.label ?? hostOf(origin.value))
/** The tag the lists are narrowed to ('' for all): a chip sets it, choosing it again or "all tags" clears it. */
const tagFilter = ref('')
const placeDocs = computed(() => filterByTag(filterListed(documents.value, query.value, shownApp.value), tagFilter.value))
const placeCount = computed(() => filterListed(documents.value, '', shownApp.value).length)
/** The tags used on this place, for the filter and for suggestions (of the app shown, if one is). */
const placeTags = computed(() => tagCounts(filterListed(documents.value, '', shownApp.value)))
watch(placeTags, (tags) => {
  if (tagFilter.value && !tags.some((c) => c.tag === tagFilter.value)) tagFilter.value = ''
})
function toggleTag(tag: string) {
  tagFilter.value = tagFilter.value === tag ? '' : tag
}
/** What the list of this place says of a document of Mine: only a document of the place shown can be looked up. */
function detailsOf(entry: MineEntry): { description?: string; tags?: string[] } {
  if (entry.origin !== origin.value) return {}
  const listed = documents.value.find((d) => d.id === entry.id && d.app === entry.app)
  return listed ? { description: listed.description, tags: listed.tags } : {}
}
const mineHere = computed(() => {
  const shown = shownCollection.value === null ? mine.value : entriesOf(collections.value.find((c) => c.name === shownCollection.value) ?? { name: '', entries: [] }, mine.value)
  const described = shown.map((e) => ({ ...e, ...detailsOf(e) }))
  return filterByTag(filterListed(described, query.value, shownApp.value), tagFilter.value)
})
const searchWords = computed(() => query.value.split(/\s+/).filter(Boolean))

// Details… of a document (sheet 10): its description and tags, changed from the list without opening it.
const editing = ref<{ id: string; app: string; description: string; tags: string[] } | null>(null)
const detailsError = ref('')
const detailsBusy = ref(false)
function editDetails(id: string, app: string) {
  const listed = documents.value.find((d) => d.id === id && d.app === app)
  detailsError.value = ''
  editing.value = { id, app, description: listed?.description ?? '', tags: [...(listed?.tags ?? [])] }
}
async function saveEditing(values: { user: string; password: string; description: string; tags: string[] }) {
  const target = editing.value
  if (!target) return
  detailsBusy.value = true
  detailsError.value = ''
  const makeLink = () =>
    new Link({
      url: socketUrl(target.id, { protocol: location.protocol, host: server.value }, target.app || undefined),
      user: values.user,
      password: values.password,
      locale: currentLocale(),
    })
  const saved = await saveDetails(makeLink, values.password, values.description, values.tags)
  detailsBusy.value = false
  if ('error' in saved) {
    detailsError.value = saved.error
    return
  }
  user.value = values.user
  documents.value = documents.value.map((d) => (d.id === target.id && d.app === target.app ? { ...d, ...saved } : d))
  editing.value = null
  notice.value = t('The description and tags of {id} are saved.', { id: target.id })
}
/** How many documents of a collection this page shows (a desktop window: only its app's). */
function shownIn(entries: string[]): number {
  return windowApp.value ? entries.filter((key) => parseKey(key)?.app === windowApp.value).length : entries.length
}
/** What the line under Open a File… says the picker takes. */
const takes = computed(() => {
  const own: Record<string, string> = {
    composes: t('Word, OpenDocument or Claudia texts, or drop one anywhere on this page.'),
    computes: t('Excel, OpenDocument or Claudia tables, or drop one anywhere on this page.'),
    creates: t('PowerPoint, OpenDocument or Claudia slides, or drop one anywhere on this page.'),
  }
  return own[windowApp.value ?? ''] ?? t('Word, Excel, PowerPoint, OpenDocument or Claudia, or drop one anywhere on this page.')
})
/** Why a desktop window does not open a file of `fileApp` (D444): it names the app the file belongs to. */
function refusalFor(fileApp: string): string {
  const belongs: Record<string, string> = {
    composes: t('This is a text. Open it with Claudia Composes.'),
    computes: t('This is a table. Open it with Claudia Computes.'),
    creates: t('These are slides. Open them with Claudia Creates.'),
  }
  return belongs[fileApp] ?? t('Claudia cannot open this file.')
}
const chosenKey = computed(() => keyOf({ origin: origin.value, app: docApp.value, id: doc.value.trim() }))
const words = computed(
  () =>
    ({
      composes: {
        headline: t('Write together.'),
        sub: t('Open a text, or start a new one. Everybody you invite writes in the same text, and so does the assistant: it suggests, you decide.'),
      },
      creates: {
        headline: t('Say it on a slide.'),
        sub: t('Open a presentation, or start a new one. Everybody you invite works on the same slides at the same time.'),
      },
    })[app.value] ?? {
      headline: t('Think with your data.'),
      sub: t('Open a table, or start a new one. Everybody you invite works in the same table, and so does the assistant.'),
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
/** The first look at the server (its apps among it): Create waits for it, so that a person — or a script — quick
 * enough to press Create before the list is there is not asked for a kind on a server of one app. */
let listed: Promise<void> = Promise.resolve()
async function loadServer() {
  listError.value = ''
  const listing = await fetchDocsListing(origin.value)
  if ('error' in listing) listError.value = listing.error
  else {
    documents.value = listing.documents
    apps.value = listing.apps
    if (apps.value.length === 1) newApp.value = apps.value[0] ?? ''
    // The server says which app it serves, and has done all along; this page used to read only the documents and
    // guess the app from the first of them, so a server with none looked like computes whatever it was serving.
    serverApp.value = listing.app
  }
  let administrator: string | null = null
  try {
    const answer = await fetch(`${origin.value}/api/admin/status`)
    if (answer.ok) administrator = (await answer.json()).administrator ?? null
  } catch {
    /* no hint this time — the bare host still makes a fine default label, and it's refreshed on the next visit */
  }
  pendingLabel = defaultLabel(origin.value, administrator)
}

/** Remember this server under `pendingLabel`: in this browser's bookmarks, or — in a shell that keeps the list — by
 * refreshing the label of its entry (the shell has added the server itself when it connected to it). Waits for the
 * shell's `welcome` and its list first. */
function settle() {
  if (!pendingLabel) return
  const bridge = shell.value
  if (inShell && bridge && !bridge.ready) return
  if (!inShell || !bridge || !bridge.hasServerList) {
    stored.value = upsertBookmark(origin.value, pendingLabel)
  } else {
    if (bridge.servers === null) return
    const entry = bridge.servers.find((b) => b.origin === origin.value)
    if (entry && !entry.custom && !entry.local && entry.label !== pendingLabel) {
      bridge.sendServers(withBookmark(bridge.servers, origin.value, pendingLabel))
    }
  }
  pendingLabel = ''
}

/** Say hello to the shell, if there is one (not before this page knows which app its server runs, when it can). */
const shellRemovers: Array<() => void> = []

/** The native menu's entries on the front page (sheet 11): File ▸ New, Open…, Open a File…, View ▸ Dark Mode and
 * Config ▸ App Language. The shell shows no others here. Each does something the person sees (D503): before, Open…
 * and New only moved the focus, which a window whose page did not have the focus did not show at all. */
function onShellAction(action: string, target?: string) {
  if (action === 'file.open-file') chooseFile()
  else if (action === 'file.open') findDocument()
  else if (action === 'file.new') startNew()
  else if (action === 'view.dark') {
    if (target === undefined || (target === 'on') !== dark()) toggleDark()
  } else if (action.startsWith('config.language.')) void chooseLanguage(action.slice('config.language.'.length))
}

/** The ticks of Dark Mode and the language, for the shell's menu (only while this page owns the bridge). */
watchEffect(() => {
  const bridge = shell.value
  if (!bridge?.ready || props.modal) return
  bridge.reportStates({
    'view.dark': { checked: dark() },
    ...Object.fromEntries(LANGUAGES.map(([tag]) => [`config.language.${tag}`, { checked: locale.value === tag }])),
  })
})
function attachShell() {
  if (!inShell) return
  if (props.modal) {
    const borrowed = props.shellBridge
    if (!borrowed) return
    shell.value = borrowed
    shellRemovers.push(
      borrowed.onConnectFailed((_code, message) => {
        connectPending.value = false
        connectError.value = message
      }),
    )
    return
  }
  const bridge = createShellBridge(isApp(app.value) ? app.value : undefined, undefined, (b) => reactive(b) as typeof b, 'start')
  bridge.onAction(onShellAction)
  // A file dropped on the window that the web view keeps from the page comes from the shell instead (D505: WebKitGTK).
  bridge.onFileOffered((file) => void takeFile(file))
  bridge.onConnectFailed((_code, message) => {
    connectPending.value = false
    connectError.value = message
  })
  shell.value = bridge
}

watch(() => [shell.value?.ready, shell.value?.hasServerList, shell.value?.servers], settle)
watch(windowApp, (own) => {
  if (own) newApp.value = own
})
onBeforeUnmount(() => {
  for (const remove of shellRemovers.splice(0)) remove()
  if (!props.modal) shell.value?.detach() // a borrowed bridge stays the document's
})

/** Ctrl+F searches, Ctrl+Shift+O opens a file (sheet 10, D); Escape leaves the collection shown (the dialog of
 * File ▸ Open has its own Escape, which closes it). */
function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && !props.modal && shownCollection.value !== null && menuFor.value === null && !typingIn(event.target)) {
    shownCollection.value = null
    return
  }
  const mod = event.ctrlKey || event.metaKey
  if (!mod || event.altKey) return
  if (event.shiftKey && event.key.toLowerCase() === 'o') {
    event.preventDefault()
    chooseFile()
  } else if (!event.shiftKey && event.key.toLowerCase() === 'f') {
    event.preventDefault()
    searchField.value?.focus()
  }
}
/** Is the key going to a field (where Escape belongs to the field)? */
function typingIn(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

/** The front page holds the presence socket while it is shown (D434, D445): it has no document's connection, and a
 * desktop server stops once nothing is connected. In File ▸ Open the document's own connection does that. */
let releasePresence: (() => void) | null = null
onMounted(() => {
  if (!props.modal) releasePresence = holdPresence(origin.value)
})
onBeforeUnmount(() => releasePresence?.())

onMounted(async () => {
  if (props.pickFile) chooseFile()
  user.value = remembered('claudia.user')
  if (!doc.value && !props.startFresh) doc.value = remembered('claudia.doc')
  if (props.startFresh) docField.value?.focus()
  listed = loadServer()
  await listed
  attachShell()
  settle()
})

function hostOf(bookmarkOrigin: string): string {
  try {
    return new URL(bookmarkOrigin).host
  } catch {
    return bookmarkOrigin
  }
}

/** Ask the shell to show another server in this window; it answers with that server's page, or with the reason why not. */
function connectInShell(address: string) {
  connectError.value = ''
  connectPending.value = true
  shell.value?.connect(address)
}

/** Go there: in a Claudia shell the shell connects (above); in a browser a full page navigation to that server's own
 * address, never an in-page fetch to another origin. */
function switchTo(bookmark: Bookmark) {
  if (bookmark.origin === origin.value) return
  if (shell.value?.canConnect) connectInShell(bookmark.origin)
  else location.href = `${bookmark.origin}/`
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
  const renaming = renamingOrigin.value
  if (renaming && viaShell.value) shell.value?.sendServers(withRenamed(bookmarks.value, renaming, renameText.value))
  else if (renaming) stored.value = renameBookmark(renaming, renameText.value)
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

/** "+ Connect to a server…". In a Claudia shell the address goes to the shell as typed (it knows what a bare host
 * means and which addresses it accepts); in a browser it is a full navigation to whatever address was typed, which
 * lands back in this same dialog at that server's own origin and bookmarks it there (`loadServer`, above). */
function goToTyped() {
  if (shell.value?.canConnect) {
    const typed = connectAddress.value.trim()
    if (typed) connectInShell(typed)
    else connectError.value = t('Type a server address.')
    return
  }
  const target = normalizeServerInput(connectAddress.value, location.protocol)
  if (!target) {
    connectError.value = t('Type a server address.')
    return
  }
  location.href = `${target}/`
}

/** Show the session at last. (What a new document starts with — a table's first sheet, a text's language — the server
 * made when it created it, as nobody's undo step: UX-33.) */
async function enter(session: AnySession) {
  remember('claudia.user', user.value.trim())
  remember('claudia.doc', doc.value.trim())
  mine.value = rememberOpened({ origin: origin.value, app: session.state.app, id: session.state.doc || doc.value.trim() })
  const imported = session.imported
  if (imported) {
    const hidden = imported.losses.reduce((sum, loss) => sum + loss.count, 0)
    session.notice(
      imported.kept
        ? hidden
          ? t('{name} is here. {count} things it holds are not shown, and stay in the kept file.', { name: imported.name, count: hidden })
          : t('{name} is here, and kept inside the document for Download.', { name: imported.name })
        : t('{name} is here. The file was not kept: Download writes a new one.', { name: imported.name }),
    )
  }
  emit('opened', session)
}

/** A document from a list: its name and its app (the address names it, D431). */
function choose(id: string, docAppName: string) {
  doc.value = id
  docApp.value = docAppName
  startingNew.value = false
}

/** A document from Mine: here, it is chosen; on another place, that place's page opens with it chosen. */
function chooseMine(entry: MineEntry) {
  if (entry.origin === origin.value) return choose(entry.id, entry.app)
  const target = `${entry.origin}/?app=${encodeURIComponent(entry.app)}&doc=${encodeURIComponent(entry.id)}`
  if (shell.value?.canConnect) connectInShell(entry.origin)
  else location.href = target
}

function forget(entry: MineEntry) {
  mine.value = forgetMine(keyOf(entry))
  collections.value = listCollections()
}

function makeCollection() {
  const name = (newCollection.value ?? '').trim()
  if (name) collections.value = createCollection(name)
  newCollection.value = null
}

function dropCollection(name: string) {
  collections.value = deleteCollection(name)
  shownCollection.value = stillShown(shownCollection.value, collections.value)
}

function toggleIn(name: string, inside: boolean) {
  collections.value = setInCollection(name, chosenKey.value, inside)
}

function isIn(name: string): boolean {
  return isInKey(name, chosenKey.value)
}

/** What names a listed document of this place in Mine and in collections. */
function placeKey(d: Listed): string {
  return keyOf({ origin: origin.value, app: d.app, id: d.id })
}

function isInKey(name: string, key: string): boolean {
  return collections.value.find((c) => c.name === name)?.entries.includes(key) ?? false
}

function toggleKey(name: string, key: string) {
  collections.value = setInCollection(name, key, !isInKey(name, key))
}

/** The bookmark button of a row: which collections the document is in, and a new one ("mine <key>" or "place <key>":
 * the same document can be a row in both lists, and only the one clicked opens). */
const menuFor = ref<string | null>(null)
const menuNewName = ref('')
async function toggleMenu(key: string) {
  menuFor.value = menuFor.value === key ? null : key
  menuNewName.value = ''
  if (menuFor.value === null) return
  await nextTick()
  document.querySelector<HTMLElement>('.collection-menu button, .collection-menu input')?.focus()
}
function newCollectionWith(key: string) {
  const name = menuNewName.value.trim()
  if (!name) return
  collections.value = createCollection(name)
  const made = collections.value.find((c) => c.name.toLowerCase() === name.toLowerCase())
  if (made && !isInKey(made.name, key)) toggleKey(made.name, key)
  menuNewName.value = ''
}
function closeMenu() {
  menuFor.value = null
}
onMounted(() => window.addEventListener('click', closeMenu))
onBeforeUnmount(() => window.removeEventListener('click', closeMenu))

/** Dragging a document onto a collection puts it in (the bookmark button does the same from the keyboard). */
const DOC_TYPE = 'application/x-claudia-document'
const dropTarget = ref<string | null>(null)
function dragDoc(event: DragEvent, key: string) {
  event.dataTransfer?.setData(DOC_TYPE, key)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'link'
}
function dropOn(name: string, event: DragEvent) {
  dropTarget.value = null
  const key = event.dataTransfer?.getData(DOC_TYPE)
  if (key && !isInKey(name, key)) toggleKey(name, key)
}
/** Only a file from the computer lights the page up as a place to drop. */
function onDragOver(event: DragEvent) {
  if (event.dataTransfer?.types.includes('Files')) dragging.value = true
}

// A name typed by hand belongs to whichever app has a document of that name here (the old address then decides); in
// a desktop window it is always a document of the window's app (D444).
watch(doc, (id) => {
  const own = windowApp.value
  const listed = documents.value.filter((d) => d.id === id.trim() && (!own || d.app === own))
  if (!listed.some((d) => d.app === docApp.value)) docApp.value = listed.length === 1 ? (listed[0]?.app ?? '') : (own ?? '')
})

/** Open a file… : the computer's own file dialog, every type Claudia opens already chosen (sheet 10, B2): the input's
 * in a browser tab, the shell's in a desktop window (D501), where the input's may not open at all. */
function chooseFile() {
  void chooseLocalFile(fileInput.value, (file) => void takeFile(file), (message) => (refusal.value = message))
}

/** The page has the focus of its window (a desktop window's menu leaves it with the window, not with the page). */
function focusPage() {
  window.focus()
}

/** File ▸ Open… on the front page (D503): the list is where documents are opened from, so the search field over it
 * gets the focus, its text selected, and comes into view. */
function findDocument() {
  focusPage()
  const field = searchField.value
  if (!field) return
  field.scrollIntoView({ block: 'nearest' })
  field.focus()
  field.select()
}

/** File ▸ New on the front page (D503): a new document starts with its name, so the Document field is emptied and gets
 * the focus, and the "start a new one" part of the form is marked until something else is done. */
const startingNew = ref(false)
function startNew() {
  focusPage()
  error.value = ''
  doc.value = ''
  startingNew.value = true
  void nextTick(() => {
    newStart.value?.scrollIntoView({ block: 'nearest' })
    docField.value?.focus()
  })
}

async function takeFile(file: File | undefined) {
  if (!file) return
  importError.value = ''
  notice.value = ''
  refusal.value = ''
  const own = windowApp.value
  const named = appOfFileName(file.name)
  if (own && named && named !== own) {
    refusal.value = refusalFor(named)
    return
  }
  // The dialog comes at once, with what the name tells; the server's answer fills in the rest.
  const dot = file.name.lastIndexOf('.')
  const extension = dot < 0 ? '' : file.name.slice(dot + 1).toLowerCase()
  incoming.value = {
    upload: '',
    name: file.name,
    format: extension,
    app: named ?? '',
    size: file.size,
    hosted: true,
    suggested_id: dot < 0 ? file.name : file.name.slice(0, dot),
  }
  importPhase.value = 'sending'
  importSent.value = 0
  const sending = sendFile(origin.value, file, (fraction) => {
    importSent.value = fraction
  })
  upload = sending
  const answer = await sending.done
  if (upload !== sending) return // given up, or another file was chosen meanwhile
  upload = null
  if ('cancelled' in answer) return
  if ('error' in answer) {
    importError.value = answer.error
    return
  }
  if (own && answer.app !== own) {
    incoming.value = null
    refusal.value = refusalFor(answer.app)
    return
  }
  incoming.value = answer
  importSent.value = 1
  importPhase.value = 'sent'
}

/** Cancel in the import dialog: stop sending, and forget the file. */
function dropIncoming() {
  upload?.abort()
  upload = null
  incoming.value = null
  importError.value = ''
}

function onPicked(event: Event) {
  const input = event.target as HTMLInputElement
  void takeFile(input.files?.[0])
  input.value = ''
}

function onDrop(event: DragEvent) {
  dragging.value = false
  void takeFile(event.dataTransfer?.files?.[0])
}

/** An Office or OpenDocument file becomes a new document (D438): the usual create, with the upload. */
async function importFile(values: { id: string; user: string; password: string; keep: boolean; description: string; tags: string[] }) {
  const file = incoming.value
  if (!file) return
  doc.value = values.id
  user.value = values.user
  password.value = values.password
  newApp.value = file.app
  importError.value = ''
  importPhase.value = 'reading'
  await go('create', { upload: file.upload, keep: values.keep, description: values.description, tags: values.tags }, () => {
    importPhase.value = 'opening'
  })
  if (error.value) {
    importError.value = error.value
    importPhase.value = 'sent' // Open again, with whatever is to be changed
  } else incoming.value = null
}

/** A Claudia file goes in as it is (D442), then is opened with its own name and password. */
async function placeFile() {
  const file = incoming.value
  if (!file) return
  busy.value = true
  importPhase.value = 'reading'
  const answer = await placeUpload(origin.value, file.upload)
  busy.value = false
  if ('error' in answer) {
    importError.value = answer.error
    importPhase.value = 'sent'
    return
  }
  incoming.value = null
  await loadServer()
  choose(answer.id, answer.app)
  notice.value = t('{id} is here now. Open it with your name and password in it.', { id: answer.id })
}

function openExisting() {
  const file = incoming.value
  incoming.value = null
  const here = file?.same_document || file?.id
  if (file && here) choose(here, file.app)
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
async function go(how: 'open' | 'create' | 'recover', from?: { upload: string; keep: boolean; description?: string; tags?: string[] }, onAnswered?: () => void) {
  error.value = ''
  startingNew.value = false
  if (how === 'create') await listed
  if (how === 'create' && !newApp.value) {
    error.value = t('Choose Table, Text or Slides first.')
    return
  }
  const missing = !doc.value.trim() || !user.value.trim() || !password.value || (how === 'recover' && !recoveryKey.value.trim())
  if (missing) {
    error.value =
      how === 'recover'
        ? t('Fill in the document, your name, the recovery key and a new password.')
        : t('Fill in the document, your name and your password.')
    return
  }
  busy.value = true
  let first = true
  const factory = () => {
    const link = new Link({
      url: socketUrl(doc.value.trim(), { protocol: location.protocol, host: server.value }, (how === 'create' ? newApp.value : docApp.value) || undefined),
      user: user.value.trim(),
      password: password.value,
      create: how === 'create' && first,
      upload: how === 'create' && first ? from?.upload : undefined,
      keepOriginal: from?.keep,
      description: how === 'create' && first ? from?.description : undefined,
      tags: how === 'create' && first ? from?.tags : undefined,
      recoveryKey: how === 'recover' && first ? recoveryKey.value.trim() : undefined,
      locale: currentLocale(),
    })
    first = false
    return link
  }
  let session: AnySession | null = null
  try {
    session = await openSession(factory, { host: server.value }, onAnswered)
    recoveryKey.value = ''
    const key = session.justCreated ? await session.newRecoveryKey({ quiet: true }) : null
    if (key) fresh.value = { session, key }
    else await enter(session)
  } catch (e) {
    const failure = e as { code?: string; message?: string } | null // a ProtocolError, or whatever a link threw
    error.value =
      failure?.code === 'unauthorized'
        ? how === 'create'
          ? t('That document exists already — or the name or password is not acceptable. Try Open.')
          : how === 'recover'
            ? t('That recovery key does not fit this document.')
            : t('The name or password is not right (or there is no such document).')
        : (failure?.message ?? t('Could not connect.'))
    session?.close()
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <component
    :is="modal ? Modal : 'main'"
    v-bind="modal ? { title: t('Open'), width: 1080 } : { class: 'open' }"
    :class="{ dragging }"
    @close="emit('close')"
    @dragover.prevent="onDragOver"
    @dragleave.self="dragging = false"
    @drop.prevent="onDrop"
  >
    <header v-if="!modal">
      <Wordmark />
      <span v-if="!isSuite" class="tag"><AppIcon :size="20" :app="app" /> {{ app }}</span>
    </header>
    <section class="card" :class="{ inside: modal }">
      <nav class="servers" :aria-label="t('My places and collections')">
        <div class="servers-title">{{ t('My places') }}</div>
        <ul>
          <li v-for="b in bookmarks" :key="b.origin">
            <input
              v-if="renamingOrigin === b.origin"
              v-model="renameText"
              class="rename"
              :aria-label="t('Rename {server}', { server: b.label })"
              autofocus
              @keydown.enter="commitRename"
              @keydown.escape="cancelRename"
              @blur="commitRename"
            >
            <template v-else>
              <button type="button" class="server" :aria-current="b.origin === origin ? 'true' : undefined" :disabled="connectPending" @click="switchTo(b)">
                <span class="server-dot" :class="{ current: b.origin === origin }" aria-hidden="true" />
                <span class="server-text">
                  <span class="server-name">{{ b.label }}</span>
                  <span class="server-host">{{ hostOf(b.origin) }}</span>
                </span>
              </button>
              <button v-if="!b.local" type="button" class="server-action" :title="t('Rename')" :aria-label="t('Rename {server}', { server: b.label })" @click="startRename(b)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" />
                </svg>
              </button>
              <button v-if="!viaShell || b.origin === origin" type="button" class="server-action" :title="t('Manage {server}…', { server: b.label })" :aria-label="t('Manage {server}…', { server: b.label })" @click="manage(b)">
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
        <button v-if="!connecting" type="button" class="connect-start" @click="startConnect">{{ t('+ Connect to a server…') }}</button>
        <form v-else class="connect-form" @submit.prevent="goToTyped">
          <input v-model="connectAddress" :aria-label="t('Server address')" :placeholder="t('example.com:8420')" autofocus >
          <div class="connect-buttons">
            <button type="submit" class="btn primary small" :disabled="connectPending">{{ t('Go') }}</button>
            <button type="button" class="btn small" @click="connecting = false">{{ t('Cancel') }}</button>
          </div>
        </form>
        <p v-if="connectPending" class="hint" role="status">{{ t('Connecting…') }}</p>
        <p v-if="connectError" class="error" role="alert">{{ connectError }}</p>
        <div class="servers-title collections-title">{{ t('Collections') }}</div>
        <ul class="collections">
          <li v-for="c in collections" :key="c.name">
            <button
              type="button"
              class="server"
              :class="{ target: dropTarget === c.name }"
              :aria-current="shownCollection === c.name ? 'true' : undefined"
              :title="shownCollection === c.name ? t('Shown now. Choose it again, or Esc, to see all documents.') : undefined"
              @click="shownCollection = nextShown(shownCollection, c.name)"
              @dragover.prevent.stop="dropTarget = c.name"
              @dragleave="dropTarget = null"
              @drop.prevent.stop="dropOn(c.name, $event)"
            >
              <svg width="12" height="15" viewBox="0 0 12 15" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M1 1h10v13l-5-4-5 4z" /></svg>
              <span class="server-text"><span class="server-name">{{ c.name }}</span></span>
              <span class="count">{{ shownIn(c.entries) }}</span>
            </button>
            <button type="button" class="server-action" :title="t('Remove collection {name}', { name: c.name })" :aria-label="t('Remove collection {name}', { name: c.name })" @click="dropCollection(c.name)">×</button>
          </li>
        </ul>
        <button v-if="newCollection === null" type="button" class="connect-start" @click="newCollection = ''">{{ t('+ New collection') }}</button>
        <form v-else class="connect-form" @submit.prevent="makeCollection">
          <input v-model="newCollection" :aria-label="t('Name of the collection')" :placeholder="t('Finance')" autofocus >
          <div class="connect-buttons">
            <button type="submit" class="btn primary small">{{ t('Make') }}</button>
            <button type="button" class="btn small" @click="newCollection = null">{{ t('Cancel') }}</button>
          </div>
        </form>
        <p class="hint kept">{{ t('Mine and the collections are kept in this browser.') }}</p>
      </nav>

      <div class="main">
        <button v-if="shownCollection !== null" type="button" class="back link" data-testid="all-documents" @click="shownCollection = null">← {{ t('All documents') }}</button>
        <h1>{{ shownCollection ?? (showsAll ? placeLabel : words.headline) }}</h1>
        <p class="sub">
          {{ shownCollection !== null ? t('The documents you put into this collection, on any place.') : showsAll ? t('Tables, texts and slides on this place, and the documents you opened before.') : words.sub }}
        </p>

        <div class="tools">
          <label class="search">
            <span class="sr-only">{{ t('Search') }}</span>
            <input ref="searchField" v-model="query" type="search" name="search" :placeholder="t('Search Mine and {place}', { place: placeLabel })" >
            <kbd>Ctrl+F</kbd>
          </label>
          <button class="btn" type="button" :disabled="busy" @click="chooseFile">{{ t('Open a File…') }}</button>
          <input ref="fileInput" class="sr-only" type="file" :accept="openableFor(windowApp)" tabindex="-1" aria-hidden="true" @change="onPicked" >
        </div>
        <p class="hint drop">{{ takes }}</p>
        <p v-if="refusal" class="error refusal" role="alert">{{ refusal }}</p>
        <p v-if="notice" class="notice" role="status">{{ notice }}</p>

        <div class="cols">
          <div>
            <div class="mine">
              <h2>{{ shownCollection === null ? t('Mine · opened before') : t('In {name}', { name: shownCollection }) }}</h2>
              <p v-if="!mineHere.length" class="hint">
                {{ shownCollection === null ? t('Nothing opened yet from this browser.') : t('Nothing in this collection yet. Add a document with the bookmark button next to it, or drag it onto the collection.') }}
              </p>
              <ul v-else>
                <li v-for="e in mineHere" :key="keyOf(e)" draggable="true" @dragstart="dragDoc($event, keyOf(e))">
                  <button type="button" class="doc" :title="e.id" :class="{ chosen: e.origin === origin && e.id === doc && e.app === docApp }" @click="chooseMine(e)">
                    <AppIcon :size="22" :app="e.app" />
                    <span class="name">{{ e.id }}</span>
                    <span class="meta">{{ e.origin === origin ? placeLabel : hostOf(e.origin) }}<template v-if="e.opened"> · {{ ago(e.opened) }}</template></span>
                  </button>
                  <div class="row-actions">
                    <button
                      v-if="e.origin === origin"
                      type="button"
                      class="server-action"
                      :title="t('Details of {id}…', { id: e.id })"
                      :aria-label="t('Details of {id}…', { id: e.id })"
                      @click="editDetails(e.id, e.app)"
                    >i</button>
                    <button
                      type="button"
                      class="server-action"
                      aria-haspopup="menu"
                      :aria-expanded="menuFor === 'mine ' + keyOf(e)"
                      :title="t('Collections of {id}…', { id: e.id })"
                      :aria-label="t('Collections of {id}…', { id: e.id })"
                      @click.stop="toggleMenu('mine ' + keyOf(e))"
                    >
                      <svg width="12" height="15" viewBox="0 0 12 15" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M1 1h10v13l-5-4-5 4z" /></svg>
                    </button>
                    <button
                      v-if="shownCollection === null"
                      type="button"
                      class="server-action"
                      :title="t('Take {id} off Mine', { id: e.id })"
                      :aria-label="t('Take {id} off Mine', { id: e.id })"
                      @click="forget(e)"
                    >×</button>
                    <button
                      v-else
                      type="button"
                      class="server-action"
                      :title="t('Take {id} out of {name}', { id: e.id, name: shownCollection })"
                      :aria-label="t('Take {id} out of {name}', { id: e.id, name: shownCollection })"
                      @click="toggleKey(shownCollection, keyOf(e))"
                    >×</button>
                  </div>
                  <DocDetails v-if="e.origin === origin" :description="e.description" :tags="e.tags" :active="tagFilter" :words="searchWords" :hint="false" @tag="toggleTag" />
                  <div v-if="menuFor === 'mine ' + keyOf(e)" class="collection-menu" role="menu" @click.stop @keydown.escape="menuFor = null">
                    <button v-for="c in collections" :key="c.name" type="button" role="menuitemcheckbox" :aria-checked="isInKey(c.name, keyOf(e))" @click="toggleKey(c.name, keyOf(e))">
                      <span class="tick" aria-hidden="true">{{ isInKey(c.name, keyOf(e)) ? '✓' : '' }}</span>{{ c.name }}
                    </button>
                    <form class="menu-new" @submit.prevent="newCollectionWith(keyOf(e))">
                      <input v-model="menuNewName" :aria-label="t('New collection')" :placeholder="t('New collection…')" >
                    </form>
                  </div>
                </li>
              </ul>
            </div>
            <div v-if="shownCollection === null" class="list">
              <div class="list-head">
                <h2>{{ isSuite ? t('On {place} · {count}', { place: placeLabel, count: placeCount }) : t('On this server') }}</h2>
                <div class="filters">
                <select v-if="placeTags.length" v-model="tagFilter" class="filter" data-testid="tag-filter" :aria-label="t('Which tags')">
                  <option value="">{{ t('all tags') }}</option>
                  <option v-for="c in placeTags" :key="c.tag" :value="c.tag">{{ c.tag }} ({{ c.count }})</option>
                </select>
                <select v-if="showsAll" v-model="appFilter" class="filter" :aria-label="t('Which apps')">
                  <option value="">{{ t('all apps') }}</option>
                  <option v-for="a in apps" :key="a" :value="a">{{ APP_WORDS[a]?.() ?? a }}</option>
                </select>
                </div>
              </div>
              <p v-if="listError" class="hint">{{ listError }}</p>
              <p v-else-if="!placeCount" class="hint">{{ t('Nothing yet. Create the first document.') }}</p>
              <ul v-else>
                <li v-for="d in placeDocs" :key="d.app + ' ' + d.id" draggable="true" @dragstart="dragDoc($event, placeKey(d))">
                  <button type="button" class="doc" :title="d.id" :class="{ chosen: d.id === doc && (!docApp || d.app === docApp), plain: !showsAll }" @click="choose(d.id, d.app)">
                    <AppIcon v-if="showsAll" :size="22" :app="d.app" />
                    <span class="name">{{ d.id }}</span>
                    <span class="meta"><template v-if="showsAll">{{ APP_WORDS[d.app]?.() ?? d.app }} · </template>{{ ago(d.modified) }}<template v-if="d.online">&nbsp;{{ t('· {online} here now', { online: d.online }) }}</template></span>
                  </button>
                  <div class="row-actions">
                    <button
                      type="button"
                      class="server-action"
                      :title="t('Details of {id}…', { id: d.id })"
                      :aria-label="t('Details of {id}…', { id: d.id })"
                      @click="editDetails(d.id, d.app)"
                    >i</button>
                    <button
                      type="button"
                      class="server-action"
                      aria-haspopup="menu"
                      :aria-expanded="menuFor === 'place ' + placeKey(d)"
                      :title="t('Collections of {id}…', { id: d.id })"
                      :aria-label="t('Collections of {id}…', { id: d.id })"
                      @click.stop="toggleMenu('place ' + placeKey(d))"
                    >
                      <svg width="12" height="15" viewBox="0 0 12 15" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M1 1h10v13l-5-4-5 4z" /></svg>
                    </button>
                  </div>
                  <DocDetails :description="d.description" :tags="d.tags" :active="tagFilter" :words="searchWords" @tag="toggleTag" />
                  <div v-if="menuFor === 'place ' + placeKey(d)" class="collection-menu" role="menu" @click.stop @keydown.escape="menuFor = null">
                    <button v-for="c in collections" :key="c.name" type="button" role="menuitemcheckbox" :aria-checked="isInKey(c.name, placeKey(d))" @click="toggleKey(c.name, placeKey(d))">
                      <span class="tick" aria-hidden="true">{{ isInKey(c.name, placeKey(d)) ? '✓' : '' }}</span>{{ c.name }}
                    </button>
                    <form class="menu-new" @submit.prevent="newCollectionWith(placeKey(d))">
                      <input v-model="menuNewName" :aria-label="t('New collection')" :placeholder="t('New collection…')" >
                    </form>
                  </div>
                </li>
              </ul>
            </div>
          </div>

        <form @submit.prevent="go(recovering ? 'recover' : 'open')">
          <label class="field">{{ t('Document') }}<input ref="docField" v-model="doc" name="document" autocomplete="off" :placeholder="t('budget-2027')" ></label>
          <label class="field">{{ t('Your name') }}<input v-model="user" name="user" autocomplete="username" :placeholder="t('ann')" ></label>
          <label v-if="recovering" class="field">
            {{ t('Recovery key') }}<input v-model="recoveryKey" name="recovery-key" autocomplete="off" spellcheck="false" :placeholder="t('ABCD-EFGH-…')" >
          </label>
          <label class="field">
            {{ recovering ? t('New password') : t('Password') }}
            <PasswordInput v-model="password" name="password" :autocomplete="recovering ? 'new-password' : 'current-password'" />
          </label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <div class="buttons">
            <template v-if="recovering">
              <button class="btn primary" type="submit" :disabled="busy">{{ t('Get back in') }}</button>
              <button class="btn" type="button" :disabled="busy" @click="recovering = false">{{ t('Back') }}</button>
            </template>
            <template v-else>
              <button class="btn primary" type="submit" :disabled="busy">{{ t('Open') }}</button>
            </template>
          </div>
          <p v-if="recovering" class="hint">
            {{ t('The recovery key was shown to the owner when the document was made (or when they made a new one). With it you choose a new password; you keep what you were allowed to do.') }}
          </p>
          <template v-else>
            <p class="hint"><button class="link" type="button" @click="recovering = true">{{ t('I forgot my password') }}</button></p>
            <fieldset v-if="docApp && collections.length" class="in-collections">
              <legend>{{ t('In collections') }}</legend>
              <label v-for="c in collections" :key="c.name" class="check">
                <input type="checkbox" :checked="isIn(c.name)" @change="toggleIn(c.name, ($event.target as HTMLInputElement).checked)" > {{ c.name }}
              </label>
            </fieldset>
            <div class="new" :class="{ wanted: startingNew }" data-testid="start-new">
              <h3>{{ t('Or start a new one') }}</h3>
              <div v-if="showsAll" class="kinds" role="radiogroup" :aria-label="t('Kind of the new document')">
                <button
                  v-for="a in apps"
                  :key="a"
                  type="button"
                  role="radio"
                  class="kind"
                  :aria-checked="newApp === a"
                  @click="newApp = a"
                >
                  <AppIcon :size="20" :app="a" /> {{ APP_WORDS[a]?.() ?? a }}
                </button>
              </div>
              <button ref="newStart" class="btn" type="button" :disabled="busy" @click="go('create')">{{ t('Create document') }}</button>
              <p class="hint">{{ t('A new document belongs to whoever creates it first. The password protects this document only (at least 8 characters, with a capital letter, a small letter and a digit).') }}</p>
            </div>
          </template>
        </form>
        </div>
      </div>
    </section>
    <RecoveryKeyDialog v-if="fresh" :recovery-key="fresh.key" :doc="doc.trim()" @done="proceed" />
    <DetailsDialog
      v-if="editing"
      :id="editing.id"
      :description="editing.description"
      :tags="editing.tags"
      :user="user"
      :place="placeLabel"
      :counts="placeTags"
      :busy="detailsBusy"
      :error="detailsError"
      @close="editing = null"
      @save="saveEditing"
    />
    <ImportDialog
      v-if="incoming"
      :file="incoming"
      :place="placeLabel"
      :user="user"
      :busy="busy"
      :error="importError"
      :phase="importPhase"
      :sent="importSent"
      :counts="placeTags"
      @close="dropIncoming"
      @import="importFile"
      @place="placeFile"
      @existing="openExisting"
    />
  </component>
</template>

<style scoped>
.open {
  height: 100%;
  display: grid;
  grid-template-rows: auto 1fr;
  background: linear-gradient(160deg, var(--paper) 55%, var(--mist));
  overflow: auto;
}
header {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 6px 28px; /* the front page is long: the card starts close under the wordmark (owner, 2026-11-14) */
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
  margin-top: 0;
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
/* the way out of a collection: first thing in the main part, so it is found before the list is */
.back {
  display: inline-block;
  margin: 0 0 10px;
  font-size: 13.5px;
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
  /* minmax(0, …): a long document name must not push the form out of the card */
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: 32px;
}
.cols form {
  min-width: 0;
}
.cols form input {
  width: 100%;
  min-width: 0;
}
.card {
  margin-bottom: 4vh;
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
.refusal {
  margin: 0 0 14px;
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
.card.inside {
  width: 100%;
  margin: 0;
  box-shadow: none;
  border: 1px solid var(--line);
}
.dragging .card {
  outline: 2px dashed var(--app);
  outline-offset: 4px;
}
.collections-title {
  margin-top: 18px;
}
.collections svg {
  flex: none;
  color: var(--muted);
}
.count {
  font: 11.5px var(--font-ui);
  color: var(--muted);
}
.kept {
  margin-top: auto;
  padding: 16px 8px 4px;
}
.tools {
  display: flex;
  gap: 12px;
  align-items: center;
}
.search {
  flex: 1;
  position: relative;
  display: flex;
}
.search input {
  flex: 1;
  padding: 9px 64px 9px 12px;
  border: 1px solid var(--line-field);
  border-radius: 9px;
  background: var(--surface);
  color: var(--text);
  font: 13.5px var(--font-ui);
}
.search kbd {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  font: 11px var(--font-mono);
  color: var(--muted);
}
.drop {
  margin: 6px 0 18px;
  text-align: right;
}
.notice {
  margin: 0 0 12px;
  padding: 8px 12px;
  border-radius: 9px;
  background: var(--app-soft);
}
.mine {
  margin-bottom: 18px;
}
.mine li,
.list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
}
.mine li,
.list li {
  position: relative;
}
.doc {
  flex: 1 1 0;
  min-width: 0;
  display: grid;
  /* the name gets the whole width and up to two lines; where and when go underneath */
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  column-gap: 10px;
  row-gap: 1px;
  text-align: left;
  border: 1px solid var(--line-field);
  background: transparent;
  border-radius: 10px;
  padding: 8px 12px;
}
.doc.plain {
  grid-template-columns: minmax(0, 1fr);
}
.doc > :not(.name, .meta) {
  grid-row: span 2;
}
.doc .name {
  overflow: hidden;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}
.doc .meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc:hover,
.doc.chosen {
  border-color: var(--app);
  background: var(--app-soft);
}
.row-actions {
  flex: none;
  display: flex;
  align-items: center;
}
/* in the flow under its row, not floating: the lists scroll, and a floating menu would be cut off by them */
.collection-menu {
  flex: 1 0 100%;
  margin: 2px 0 4px;
  display: grid;
  gap: 2px;
  padding: 6px;
  background: var(--surface);
  border: 1px solid var(--line-field);
  border-radius: 10px;
  box-shadow: var(--shadow);
}
.collection-menu button {
  display: flex;
  gap: 8px;
  padding: 6px 8px;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--text);
  text-align: left;
  font: 13px var(--font-ui);
  cursor: pointer;
}
.collection-menu button:hover,
.collection-menu button:focus-visible {
  background: var(--app-soft);
}
.tick {
  width: 14px;
  color: var(--app-text);
}
.menu-new input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--line-field);
  border-radius: 7px;
  background: var(--surface);
  color: var(--text);
  font: 13px var(--font-ui);
}
.server.target {
  outline: 2px dashed var(--app);
}
.list-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.filters {
  display: flex;
  gap: 8px;
}
.filter {
  font: 12px var(--font-ui);
  color: var(--app-text);
  background: transparent;
  border: none;
}
.new {
  display: grid;
  gap: 10px;
  margin-top: 8px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
/* File ▸ New (D503): the part of the form that makes a new document, marked until the person does something else */
.new.wanted {
  border-top-color: var(--iris);
  box-shadow: inset 3px 0 0 var(--iris);
  padding-left: 10px;
}
h3 {
  font: 600 13px var(--font-ui);
  margin: 0;
}
.kinds {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.kind {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  border: 1px solid var(--line-field);
  border-radius: 9px;
  background: var(--surface);
  color: var(--text);
  font: 500 12.5px var(--font-ui);
  cursor: pointer;
}
.kind[aria-checked='true'] {
  border-width: 2px;
  border-color: var(--text);
  font-weight: 600;
}
.in-collections {
  border: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 4px;
}
.in-collections legend {
  font: 500 12px var(--font-ui);
  color: var(--muted);
  margin-bottom: 4px;
}
.check {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
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
