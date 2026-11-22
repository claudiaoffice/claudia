<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ChatInput from './ChatInput.vue'
import { clock, colorOf, inkOn } from '~/lib/people'
import { useI18n } from '~/lib/i18n'
import type { BaseSession, ChatMessage, Step } from '~/lib/base-session'
import type { AiMode } from '~/lib/ai-mode'
import { rowKey } from '~/lib/base-session'
import { keyStep, WheelStepper, wheelDelta, type Filter } from '~/lib/replay'
import { tintsOf } from '~/lib/replay-tint'
import { ChatPick, POINTER_EVENTS, type PointerKind } from '~/lib/chat-pick'
import { auditSentence, type AuditRow } from '~/lib/audit'
import { hashAt, insertTag, matches, splitTags, withCurrentNames, withTag, type Thing, type ThingKind } from '~/lib/tags'
import {
  REDACTION_KIND,
  mayRedact,
  mayRedactEntry,
  mayRedactMessage,
  nothingPicked,
  pickedCount,
  spokenFiller,
  togglingEntry,
  togglingMessage,
  type Picked,
} from '~/lib/redaction'
import ContextMenu from './ContextMenu.vue'
import type { MenuItem } from './MenuBar.vue'

const props = defineProps<{ session: BaseSession }>()
/** `redact`: the person asked to redact what is picked (E3.14); the window opens the dialog for it. */
const emit = defineEmits<{ redact: [picked: Picked] }>()
const state = props.session.state
// `t` stays this bare (never `i18n.t`): `scripts/extract_i18n.py`'s own regex only recognises an unqualified
// `t(...)` call (`obj.t(...)` is deliberately excluded, the same way `format(...)` is) -- see its docstring. Only
// the two static headers below need it; this panel has no Config ▸ App Language menu of its own.
const { t } = useI18n()

const history = ref<HTMLElement | null>(null)
const chatLog = ref<HTMLElement | null>(null)
const input = ref<InstanceType<typeof ChatInput> | null>(null)
const draft = ref('')

/** The two ways the AI can treat a request (D262), in every app (D640). */
const modes: { mode: AiMode; label: string }[] = [
  { mode: 'act', label: t('Act at once') },
  { mode: 'suggest', label: t('Suggest first') },
]
/** A radio group moves with the arrow keys and is one tab stop (WAI-ARIA radio group): the checked one. */
function onModeKey(event: KeyboardEvent) {
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key]
  if (!step) return
  event.preventDefault()
  const at = modes.findIndex((m) => m.mode === state.aiMode)
  const next = modes[(at + step + modes.length) % modes.length]!
  props.session.setAiMode(next.mode)
  void nextTick(() => (event.currentTarget as HTMLElement | null)?.querySelector<HTMLElement>(`[data-mode="${next.mode}"]`)?.focus())
}

// ------------------------------------------------------------------------------ the two tabs (E13.5; the chat/history
// redesign discussed alongside the help system is deferred — this tab strip is the one piece of that discussion
// that ships now, so the new "Help" tab has somewhere to live without touching History & Chat itself).
const tab = ref<'history' | 'help'>('history')
const helpPanel = ref<{ focus: (mode?: 'how-to' | 'docs') => void; showTopic: (id: string) => Promise<void> } | null>(null)

/** Help ▸ "How do I…?" and Help ▸ "Documentation" (D125's stubs, now real): switch to the Help tab and its
 * matching section. With a `topic` (an id, `composes.searching-and-replacing`) the topic itself opens, which is what a
 * link from inside the app, like the search panel's "About searching and patterns", asks for. */
function openHelp(mode?: 'how-to' | 'docs', topic?: string) {
  tab.value = 'help'
  nextTick(() => (topic ? helpPanel.value?.showTopic(topic) : helpPanel.value?.focus(mode)))
}

/** The history with the checkpoints in their places. */
const rows = computed(() => {
  const marks = new Map<string, typeof state.checkpoints>()
  for (const c of state.checkpoints) marks.set(c.marks, [...(marks.get(c.marks) ?? []), c])
  const out: (
    | { kind: 'entry'; entry: (typeof state.entries)[number] }
    | { kind: 'mark'; label: string; author: string | null; number: number }
    | { kind: 'left'; row: AuditRow }
  )[] = []
  // What left the document has no revision (D1271): the time alone says where among the changes its line goes.
  const left = [...state.audit].sort((a, b) => Date.parse(a.when) - Date.parse(b.when))
  let next = 0
  for (const entry of state.entries) {
    while (next < left.length && Date.parse(left[next]!.when) < Date.parse(entry.time)) out.push({ kind: 'left', row: left[next++]! })
    out.push({ kind: 'entry', entry })
    for (const c of marks.get(entry.revision) ?? []) out.push({ kind: 'mark', label: c.label || `checkpoint ${c.number}`, author: c.author, number: c.number })
  }
  while (next < left.length) out.push({ kind: 'left', row: left[next++]! })
  return out
})

// ------------------------------------------------------------------------------ replaying the history (E5.19, D551)
const replay = computed(() => state.replay)
const stepper = new WheelStepper()
const filters: { id: Filter; label: string }[] = [
  { id: 'all', label: t('All') },
  { id: 'steps', label: t('Steps') },
  { id: 'chat', label: t('Chat') },
]
const canReplay = computed(() => state.status === 'open' && state.entries.length > 0)
/** The rows the playhead can visit with the current filter, by key. */
const visited = computed(() => new Set(state.replay ? props.session.replayItems().map(rowKey) : []))
/** Where the playhead is, as a place in the order of the revisions, so rows after it can be dimmed. */
const sequence = (revision: string) => Number(revision.slice(revision.lastIndexOf(':') + 1))
const afterPlayhead = (revision: string) => replay.value !== null && sequence(revision) > sequence(replay.value.revision)
const position = computed(() => {
  const at = state.replay ? props.session.replayIndex() : -1
  return at < 0 ? '' : t('Step {at} of {total}', { at: at + 1, total: props.session.replayItems().length })
})
/** What a screen reader hears when the playhead moves. */
const announcement = computed(() => {
  const r = state.replay
  if (!r) return ''
  const item = props.session.replayItems().find((i) => rowKey(i) === r.row)
  if (!item) return ''
  const what = item.kind === 'change' ? item.summary : item.text
  return `${position.value}: ${item.author ?? '?'} — ${what}`
})

function isCurrent(key: string): boolean {
  return state.replay?.row === key
}
function visit(key: string) {
  const at = props.session.replayItems().findIndex((i) => rowKey(i) === key)
  if (at >= 0) void props.session.replayGo(at)
}
function toggleReplay() {
  void (state.replay ? props.session.endReplay() : props.session.startReplay())
}

/** The wheel over History & Chat steps the playhead; Ctrl+wheel scrolls as before. Wheeling up from the present starts a
 * replay; wheeling down in the present scrolls the lists as usual. */
function onWheel(event: WheelEvent) {
  if (event.ctrlKey || tab.value !== 'history') return
  const delta = wheelDelta(event)
  if (!state.replay && (delta >= 0 || !canReplay.value)) return
  const steps = stepper.feed(delta)
  event.preventDefault()
  if (steps === 0) return
  const unit = event.shiftKey ? 'author' : 'row'
  const by = steps > 0 ? 1 : -1
  const begin = state.replay ? Promise.resolve() : props.session.startReplay()
  void begin.then(() => {
    for (let i = 0; i < Math.abs(steps); i++) void props.session.replayStep(by, unit)
  })
}
function onKey(event: KeyboardEvent) {
  // Escape and End belong to the text box while somebody is typing in it
  const typing = (event.target as HTMLElement | null)?.closest('input, textarea') !== null
  if (typing && !event.altKey) return
  const move = keyStep(event)
  if (!move || (!state.replay && !('by' in move && canReplay.value))) return
  event.preventDefault()
  if ('by' in move) {
    const begin = state.replay ? Promise.resolve() : props.session.startReplay()
    void begin.then(() => props.session.replayStep(move.by))
  } else if (move.to === 'now') void props.session.endReplay()
  else void props.session.replayGo(0)
}
watch(
  () => state.replay?.row,
  async (row) => {
    if (!row) return
    stepper.reset()
    await nextTick()
    for (const list of [history.value, chatLog.value]) {
      const el = list?.querySelector<HTMLElement>(`[data-row="${CSS.escape(row)}"]`)
      el?.scrollIntoView({ block: 'nearest' })
    }
  },
)
/** View ▸ Replay history…: the history tab, with the playhead at the latest change. */
function startReplay() {
  tab.value = 'history'
  void props.session.startReplay()
}
defineExpose({ ask, openHelp, replay: startReplay, reference: referenceThing, pickToRedact, clearRedactionPick })

// ------------------------------------------------------------------------------ picking what to redact (E3.14, D727)
const me = computed(() => ({ user: state.me.user, role: state.me.role }))
const redacts = computed(() => mayRedact(me.value) && !state.replay && !state.preview)
/** Pick boxes on every row: File ▸ Manage ▸ Redact History…, or a Ctrl+click on a row. */
const picking = ref(false)
const picked = ref<Picked>(nothingPicked())
const pickCount = computed(() => pickedCount(picked.value))
const menu = ref<{ x: number; y: number } | null>(null)

const isPickedEntry = (revision: string) => picked.value.revisions.includes(revision)
const isPickedMessage = (number: number) => picked.value.chat.includes(number)
const canPickEntry = (entry: Step) => redacts.value && mayRedactEntry(entry, me.value)
const canPickMessage = (message: ChatMessage) => redacts.value && mayRedactMessage(message, me.value)
const notYours = computed(() => (state.me.role === 'owner' ? t('There is nothing in this to redact.') : t('You can redact only your own work.')))

/** File ▸ Manage ▸ Redact History…: the history tab, with a pick box on every row. */
function pickToRedact() {
  tab.value = 'history'
  picking.value = true
}
/** After a redaction, or when the person gives up picking. */
function clearRedactionPick() {
  picked.value = nothingPicked()
  picking.value = false
  menu.value = null
}
function pickEntry(entry: Step) {
  if (canPickEntry(entry)) picked.value = togglingEntry(picked.value, entry.revision)
}
function pickMessage(message: ChatMessage) {
  if (canPickMessage(message)) picked.value = togglingMessage(picked.value, message.number)
}
/** Ctrl+click (Cmd+click) picks a row and shows the pick boxes; a plain click in a replay still visits. */
function onEntryClick(event: MouseEvent, entry: Step) {
  if ((event.ctrlKey || event.metaKey) && canPickEntry(entry)) {
    event.preventDefault()
    picking.value = true
    pickEntry(entry)
  } else if (replay.value) visit('c:' + entry.revision)
}
function onMessageClick(event: MouseEvent, message: ChatMessage) {
  if (!(event.ctrlKey || event.metaKey) || !canPickMessage(message)) return
  event.preventDefault()
  picking.value = true
  pickMessage(message)
}
/** The right-click menu of a row: the row joins the pick, and "Redact n items…" is offered. */
function onEntryMenu(event: MouseEvent, entry: Step) {
  if (!canPickEntry(entry)) return
  event.preventDefault()
  if (!isPickedEntry(entry.revision)) pickEntry(entry)
  menu.value = { x: event.clientX, y: event.clientY }
}
function onMessageMenu(event: MouseEvent, message: ChatMessage) {
  if (!canPickMessage(message)) return
  event.preventDefault()
  if (!isPickedMessage(message.number)) pickMessage(message)
  menu.value = { x: event.clientX, y: event.clientY }
}
const menuItems = computed<MenuItem[]>(() => [
  { label: t('Redact… ({n} picked)', { n: pickCount.value }), hint: 'Shift+Del', action: askToRedact },
  { label: t('Pick more…'), action: () => (picking.value = true) },
  { label: '', separator: true },
  { label: t('Clear the pick'), action: clearRedactionPick },
])
function askToRedact() {
  menu.value = null
  if (pickCount.value) emit('redact', picked.value)
}
/** Shift+Delete anywhere in History & Chat redacts what is picked. */
function onPickKey(event: KeyboardEvent) {
  if (event.key !== 'Delete' || !event.shiftKey || !pickCount.value) return
  if ((event.target as HTMLElement | null)?.closest('textarea, input:not([type=checkbox])')) return
  event.preventDefault()
  askToRedact()
}
const isRecord = (entry: Step) => entry.kind === REDACTION_KIND
/** What a redacted row says to a screen reader: who and when, and the filler as lengths. */
function redactedLabel(entry: Step): string {
  return t('Redacted: {what}, by {who} at {time}', { what: spokenFiller(entry.summary, t), who: entry.author ?? '?', time: clock(entry.time) })
}

// ------------------------------------------------------------------------------ tags: `#` in the chat (E5.20, D551)
const caret = ref(0)
const hash = computed(() => hashAt(draft.value, caret.value))
/** What `#` offers, read from the document when it opens. */
const offered = ref<Thing[]>([])
const unnamed = ref(0)
const dismissed = ref<number | null>(null)
const active = ref(0)
const suggestions = computed(() => (hash.value && dismissed.value !== hash.value.start ? matches(offered.value, hash.value.query) : []))
/** The last row of the list: name what has no name yet, so that it can be pointed at. */
const offerNaming = computed(() => hash.value !== null && dismissed.value !== hash.value.start && unnamed.value > 0)
const optionCount = computed(() => suggestions.value.length + (offerNaming.value ? 1 : 0))
const listOpen = computed(() => optionCount.value > 0)
const kindLabels: Record<ThingKind, string> = {
  text: t('Text box'),
  shape: t('Shape'),
  image: t('Picture'),
  diagram: t('Chart'),
  container: t('Container'),
  table: t('Table'),
  slide: t('Slide'),
  sheet: t('Sheet'),
  chart: t('Chart'),
  range: t('Range'),
  heading: t('Heading'),
  item: t('List item'),
  paragraph: t('Paragraph'),
}
const optionId = (i: number) => `tag-option-${i}`

async function readThings() {
  offered.value = await props.session.taggableThings()
  unnamed.value = await props.session.unnamedInView()
}
watch(
  () => hash.value?.start ?? null,
  (start) => {
    active.value = 0
    if (start === null) dismissed.value = null
    else void readThings()
  },
)
watch(() => hash.value?.query, () => (active.value = 0))

async function pickThing(offeredThing: Thing) {
  const h = hash.value
  if (!h) return
  // a paragraph without a name gets one first (D554): the tag must name what the document calls it
  const thing = offeredThing.unnamed ? await props.session.thingToReference(offeredThing.id) : offeredThing
  if (!thing) return
  const done = withTag(draft.value, h, caret.value, thing)
  draft.value = done.text
  caret.value = done.caret
  void nextTick(() => {
    input.value?.focus()
    input.value?.setCaret(done.caret)
  })
}
async function nameThem() {
  await props.session.nameUnnamed()
  await readThings()
}
function pickOption(i: number) {
  const thing = suggestions.value[i]
  if (thing) void pickThing(thing)
  else if (offerNaming.value) void nameThem()
}
/** The keys of a combobox: arrows move, Enter and Tab pick, Escape closes the list and the `#…` stays plain text. */
function onChatKey(event: KeyboardEvent) {
  if (!listOpen.value || event.isComposing) return
  const n = optionCount.value
  if (event.key === 'ArrowDown') active.value = (active.value + 1) % n
  else if (event.key === 'ArrowUp') active.value = (active.value + n - 1) % n
  else if (event.key === 'Enter' || event.key === 'Tab') pickOption(active.value)
  else if (event.key === 'Escape') dismissed.value = hash.value?.start ?? null
  else return
  event.preventDefault()
  event.stopPropagation()
}
const announceList = computed(() =>
  listOpen.value ? t('{n} things to point at. Use the arrow keys, then Enter.', { n: suggestions.value.length }) : '',
)
function segmentsOf(text: string) {
  return splitTags(text)
}
function tagName(id: string, written: string): string {
  return props.session.nameOf(id) ?? written
}
function goTo(id: string) {
  void props.session.goToThing(id)
}
/** Edit ▸ Reference in Chat, and a click on a thing while the box has the caret: a tag for the thing goes in at the caret. */
function referenceThing(thing: Thing) {
  tab.value = 'history'
  const at = caret.value > draft.value.length || !chatFocused.value ? draft.value.length : caret.value
  const done = insertTag(draft.value, at, thing)
  draft.value = done.text
  caret.value = done.caret
  void nextTick(() => {
    input.value?.focus()
    input.value?.setCaret(done.caret)
  })
}

// Click to tag: while the box has the caret, a click on a thing in the document writes its tag (`lib/chat-pick.ts`).
const chatFocused = ref(false)
const gate = new ChatPick(() => chatFocused.value)
function onPointer(event: Event) {
  const verdict = gate.handle(event.type as PointerKind, event.target)
  if (verdict === 'pass') return
  event.preventDefault() // (the caret stays in the box)
  event.stopImmediatePropagation() // (and the document does not get the click)
  if (verdict !== 'swallow') void pickFromDocument(verdict.pick)
}
async function pickFromDocument(id: string) {
  const thing = await props.session.thingToReference(id)
  if (thing) referenceThing(thing)
}
watch(chatFocused, (focused) => {
  document.documentElement.classList.toggle('picking', focused)
  if (!focused) gate.reset()
})
onMounted(() => {
  for (const type of POINTER_EVENTS) window.addEventListener(type, onPointer, true)
})
onBeforeUnmount(() => {
  for (const type of POINTER_EVENTS) window.removeEventListener(type, onPointer, true)
  document.documentElement.classList.remove('picking')
})

const others = computed(() => state.typing.filter((u) => u !== state.me.user))

// ------------------------------------------------------------------------------ lines, and restoring with consent (E3.7, E3.8)
const canWrite = computed(() => state.me.role === 'owner' || state.me.role === 'editor')
const viewer = computed(() => state.me.role === 'viewer')  // holds the content key only: no history, no chat (D1261)
const isOwner = computed(() => state.me.role === 'owner')
const hiddenBranches = computed(() => state.branches.filter((b) => !b.active))
const myProposal = computed(() => state.proposal)
const canWithdraw = computed(() => myProposal.value && (myProposal.value.by === state.me.user || isOwner.value))
const haveAgreed = computed(() => myProposal.value?.agreed.includes(state.me.user) ?? false)
const stillWaitingOn = computed(() => myProposal.value ? myProposal.value.group.filter((u) => !myProposal.value!.agreed.includes(u)) : [])

type Peeked = Exclude<Awaited<ReturnType<BaseSession['peekBranch']>>, false>
const peeked = ref<Record<string, Peeked>>({})
async function togglePeek(branch: string) {
  if (peeked.value[branch]) {
    const { [branch]: _drop, ...rest } = peeked.value
    peeked.value = rest
    return
  }
  const result = await props.session.peekBranch(branch)
  if (result) peeked.value = { ...peeked.value, [branch]: result }
}

function suggestRestore(checkpoint: number) {
  void props.session.proposeRestore(checkpoint)
}
function suggestRestoreStep() {
  void props.session.proposeRestoreStep()
}
/** How many places differ from now, said in words (the tint itself is only for those who see it). */
const differenceNote = computed(() => {
  const r = state.replay
  if (!r) return ''
  const n = tintsOf([], r.changed).count
  if (n === 0) return t('Nothing differs from now')
  return r.changedMore ? t('More than {n} places differ from now', { n }) : t('Places that differ from now: {n}', { n })
})
function suggestSwitch(branch: string) {
  void props.session.proposeSwitch(branch)
}
function agree() {
  void props.session.answerRestore(true)
}
function decline() {
  void props.session.answerRestore(false)
}
function withdraw() {
  void props.session.withdrawRestore()
}
function discard() {
  void props.session.discardSideHistory()
}
function setPolicy(policy: 'consensus' | 'veto') {
  void props.session.setRestorePolicy(policy)
}

async function toBottom(el: HTMLElement | null) {
  await nextTick()
  if (el) el.scrollTop = el.scrollHeight
}
watch(() => rows.value.length, () => toBottom(history.value))
watch(() => state.chat.length, () => toBottom(chatLog.value))
watch(() => state.typing.length, () => toBottom(chatLog.value))

async function send() {
  const text = withCurrentNames(draft.value, (id) => props.session.nameOf(id)).trim()
  if (!text) return
  if (await props.session.say(text)) draft.value = ''
}

/** Tools ▸ Ask AI: put the cursor in the chat box, ready to write to the assistant. */
function ask(prefill = '@ai ') {
  tab.value = 'history'
  draft.value = prefill
  nextTick(() => {
    input.value?.focus()
    input.value?.setCaret(draft.value.length)
  })
}

const isAi = (user: string) => user.toLowerCase() === 'ai'
</script>

<template>
  <aside class="panel" :class="{ replaying: replay }" :aria-label="t('document panel')" @keydown="onKey($event), onPickKey($event)">
    <slot name="top" />

    <!-- How the AI treats my requests here (D262): directly above the tabs, so it reads as a setting of the whole
         panel rather than of one chat message (owner's request, 2026-11-12). -->
    <div class="aiMode" data-testid="ai-mode">
      <span id="ai-mode-label">{{ t('When I ask the AI, in this document:') }}</span>
      <div class="segmented" role="radiogroup" aria-labelledby="ai-mode-label" @keydown="onModeKey">
        <button
          v-for="m in modes"
          :key="m.mode"
          type="button"
          role="radio"
          :data-mode="m.mode"
          :aria-checked="state.aiMode === m.mode"
          :tabindex="state.aiMode === m.mode ? 0 : -1"
          @click="session.setAiMode(m.mode)"
        >{{ m.label }}</button>
      </div>
    </div>

    <div class="tabs" role="tablist">
      <button type="button" role="tab" :aria-selected="tab === 'history'" :class="{ active: tab === 'history' }" @click="tab = 'history'">{{ t('History & Chat') }}</button>
      <button type="button" role="tab" :aria-selected="tab === 'help'" :class="{ active: tab === 'help' }" @click="tab = 'help'">{{ t('Help') }}</button>
    </div>

    <div v-show="tab === 'history'" class="historyChat" :aria-label="t('history and chat')" @wheel="onWheel">
    <p v-if="viewer" class="viewerNote" data-testid="viewer-note">{{ t('History and chat are for the document\'s editors.') }}</p>
    <template v-else>
    <div v-if="myProposal" class="proposal" role="alert">
      <p class="ask">
        <TransText :text="t('{who} suggests going to {line}.', { line: myProposal.label })"><template #who><b>{{ myProposal.by }}</b></template></TransText>
        <span v-if="stillWaitingOn.length" class="waiting">{{ t('Waiting on {names}.', { names: stillWaitingOn.join(', ') }) }}</span>
      </p>
      <div class="buttons">
        <button v-if="canWrite && !haveAgreed" type="button" class="agree" @click="agree">{{ t('Agree') }}</button>
        <button v-if="canWrite" type="button" class="decline" @click="decline">{{ t('Decline') }}</button>
        <button v-if="canWithdraw" type="button" class="withdraw" @click="withdraw">{{ t('Withdraw') }}</button>
      </div>
    </div>

    <section class="history">
      <h2>
        {{ t('History') }} <span class="count">{{ state.entries.length }}</span>
        <button type="button" class="replayBtn" :aria-pressed="replay !== null" :disabled="!replay && !canReplay" :title="t('Replay the history: wheel over this panel, or Alt+Page Up')" @click="toggleReplay">{{ replay ? t('Back to now') : t('Replay') }}</button>
      </h2>
      <div v-if="replay" class="replayBar" data-testid="replay-bar">
        <div class="segmented" role="radiogroup" :aria-label="t('Which steps the wheel visits')">
          <button
            v-for="f in filters"
            :key="f.id"
            type="button"
            role="radio"
            :aria-checked="replay.filter === f.id"
            @click="session.setReplayFilter(f.id)"
          >{{ f.label }}</button>
        </div>
        <label class="follow"><input type="checkbox" :checked="replay.follow" @change="session.setReplayFollow(($event.target as HTMLInputElement).checked)"> {{ t('Follow changes') }}</label>
        <label class="follow" :title="t('Mark where the document changed after this step: solid outlines are what this step changed, dashed ones what changed later')"><input type="checkbox" :checked="replay.differences" @change="session.setReplayDifferences(($event.target as HTMLInputElement).checked)"> {{ t('Show differences from now') }}</label>
        <span v-if="replay.differences" class="differs" role="status">{{ differenceNote }}</span>
        <button v-if="canWrite && !myProposal" type="button" class="suggest" :title="t('Suggest going back to the document as it was after this step')" @click="suggestRestoreStep">{{ t('↺ restore this step') }}</button>
        <span class="where" aria-hidden="true">{{ position }}<template v-if="replay.loading"> …</template></span>
        <span v-if="replay.newer" class="newer">{{ t('{n} newer changes by others', { n: replay.newer }) }}</span>
        <p class="sr-only" role="status" aria-live="polite" aria-atomic="true">{{ announcement }}</p>
      </div>
      <div v-if="redacts && (picking || pickCount)" class="pickBar" data-testid="redaction-pick">
        <span role="status">{{ pickCount ? t('Picked to redact: {n}', { n: pickCount }) : t('Pick the changes and messages to redact.') }}</span>
        <button type="button" class="redactBtn" :disabled="!pickCount" :title="t('Shift+Del')" @click="askToRedact">{{ t('Redact…') }}</button>
        <button type="button" class="cancelPick" @click="clearRedactionPick">{{ t('Cancel') }}</button>
      </div>
      <ol ref="history" class="log mono" :aria-label="t('everything that was done to this document')">
        <li v-if="!rows.length" class="empty">{{ state.app === 'composes' ? t('Nothing yet. Start writing.') : state.app === 'creates' ? t('Nothing yet. Put a text box on the slide.') : t('Nothing yet. Type into a cell.') }}</li>
        <template v-for="(row, i) in rows" :key="i">
          <li
            v-if="row.kind === 'entry'"
            class="entry"
            :class="{ undo: row.entry.origin !== 'do', current: isCurrent('c:' + row.entry.revision), later: afterPlayhead(row.entry.revision), skipped: replay && !visited.has('c:' + row.entry.revision), redacted: row.entry.redacted, record: isRecord(row.entry), picked: isPickedEntry(row.entry.revision), picking: redacts && picking }"
            :data-row="'c:' + row.entry.revision"
            @contextmenu="onEntryMenu($event, row.entry)"
          >
            <input
              v-if="redacts && picking"
              type="checkbox"
              class="pick"
              :checked="isPickedEntry(row.entry.revision)"
              :disabled="!canPickEntry(row.entry)"
              :title="canPickEntry(row.entry) ? t('Pick for redaction') : notYours"
              :aria-label="t('Pick for redaction: {what}', { what: row.entry.redacted ? redactedLabel(row.entry) : row.entry.summary })"
              @change="pickEntry(row.entry)"
            >
            <component :is="replay ? 'button' : 'div'" class="entryRow" :type="replay ? 'button' : undefined" :aria-current="isCurrent('c:' + row.entry.revision) ? 'step' : undefined" :aria-label="row.entry.redacted ? redactedLabel(row.entry) : undefined" @click="onEntryClick($event, row.entry)">
              <span v-if="isRecord(row.entry)" class="eraser" aria-hidden="true"><svg viewBox="0 0 12 12" width="10" height="10"><path d="M1 8.5 6 3.5l4 4-2.5 2.5h-4z M3.5 6l4 4" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round" /></svg></span>
              <span v-else class="dot" :class="{ hatched: row.entry.redacted }" :style="row.entry.redacted ? undefined : { background: colorOf(state, row.entry.author ?? '') }" />
              <span class="who">{{ row.entry.author ?? '?' }}</span>
              <span class="what" :title="row.entry.redacted ? t('Redacted: the content of this change was taken away.') : row.entry.label">
                <em v-if="row.entry.origin !== 'do'">{{ row.entry.origin }} · </em>{{ row.entry.summary }}
              </span>
              <time>{{ clock(row.entry.time) }}</time>
            </component>
          </li>
          <li v-else-if="row.kind === 'left'" class="left" data-testid="audit-row">
            <span class="who">{{ row.row.who }}</span>
            <span class="what">{{ auditSentence(row.row) }}</span>
            <time>{{ clock(row.row.when) }}</time>
          </li>
          <li v-else class="mark">
            <span>{{ t('◆ saved: {label}', { label: row.label }) }}<template v-if="row.author"> · {{ row.author }}</template></span>
            <button v-if="canWrite && !myProposal" type="button" class="suggest" :title="t('Suggest going back to this checkpoint')" @click="suggestRestore(row.number)">{{ t('↺ restore') }}</button>
          </li>
        </template>
      </ol>
    </section>

    <section v-if="state.branches.length > 1 || hiddenBranches.length" class="branches">
      <h2>
        {{ t('Branches') }} <span class="count">{{ state.branches.length }}</span>
        <select v-if="isOwner" class="policy" :value="state.restorePolicy" :title="t('What silence at a suggestion\'s deadline means')" @change="setPolicy(($event.target as HTMLSelectElement).value as 'consensus' | 'veto')">
          <option value="consensus">{{ t('silence = decline') }}</option>
          <option value="veto">{{ t('silence = agree') }}</option>
        </select>
      </h2>
      <ol class="branchList">
        <li v-for="branch in state.branches" :key="branch.name" class="branch" :class="{ active: branch.active }">
          <span class="name"><span v-if="branch.active" class="dot" />{{ branch.name }}</span>
          <span class="actions">
            <button type="button" @click="togglePeek(branch.name)">{{ peeked[branch.name] ? t('close') : t('peek') }}</button>
            <button v-if="!branch.active && canWrite && !myProposal" type="button" @click="suggestSwitch(branch.name)">{{ t('suggest switching here') }}</button>
          </span>
          <pre v-if="peeked[branch.name]" class="peekBox mono">{{ JSON.stringify(peeked[branch.name]!.state, null, 1) }}</pre>
        </li>
      </ol>
      <button v-if="isOwner && hiddenBranches.length && !myProposal" type="button" class="discard" @click="discard">{{ t('Forget every hidden branch') }}</button>
    </section>

    <section class="chat">
      <h2>{{ t('Chat') }}</h2>
      <ol ref="chatLog" class="messages" aria-live="polite">
        <li v-if="!state.chat.length" class="empty"><TransText :text="t('Write to everybody, or {ask} to ask the assistant. Say {help} to see what it can do.')"><template #ask><b>@ai</b></template><template #help><b>@ai help</b></template></TransText></li>
        <li
          v-for="m in state.chat"
          :key="m.number"
          class="msg"
          :class="{ ai: isAi(m.author), mine: m.author === state.me.user, current: isCurrent('m:' + m.number), skipped: replay && !visited.has('m:' + m.number), redacted: m.redacted, picked: isPickedMessage(m.number) }"
          :data-row="'m:' + m.number"
          @contextmenu="onMessageMenu($event, m)"
          @click="onMessageClick($event, m)"
        >
          <header>
            <input
              v-if="redacts && picking"
              type="checkbox"
              class="pick"
              :checked="isPickedMessage(m.number)"
              :disabled="!canPickMessage(m)"
              :title="canPickMessage(m) ? t('Pick for redaction') : notYours"
              :aria-label="t('Pick for redaction: message by {who} at {time}', { who: m.author, time: clock(m.time) })"
              @click.stop
              @change="pickMessage(m)"
            >
            <span class="author" :style="{ background: colorOf(state, m.author), color: inkOn(colorOf(state, m.author)) }">{{ m.author }}</span>
            <span v-if="m.to" class="to">→ {{ m.to }}</span>
            <time>{{ clock(m.time) }}</time>
            <button v-if="replay" type="button" class="visit" :aria-current="isCurrent('m:' + m.number) ? 'step' : undefined" :aria-label="t('Show the document as it was at this message')" @click="visit('m:' + m.number)">{{ isCurrent('m:' + m.number) ? t('▶ here') : t('▷ go here') }}</button>
          </header>
          <p v-if="m.redacted" class="gone">{{ t('Message redacted') }}</p>
          <p v-else><template v-for="(seg, k) in segmentsOf(m.text)" :key="k"><template v-if="seg.type === 'text'">{{ seg.text }}</template><button v-else type="button" class="tag" :class="{ gone: session.isGone(seg.id) }" :title="session.isGone(seg.id) ? t('Deleted. Show the last moment it was there.') : t('Go to this')" @click="goTo(seg.id)">#{{ tagName(seg.id, seg.name) }}</button></template></p>
        </li>
        <li v-if="others.length" class="typing">
          <span class="author" :style="{ background: colorOf(state, others[0]!), color: inkOn(colorOf(state, others[0]!)) }">{{ others[0] }}</span>
          {{ t('is working') }}<span class="dots"><i /><i /><i /></span>
        </li>
      </ol>
      <form class="write" @submit.prevent="send">
        <ul v-if="listOpen" id="tag-list" class="tagList" role="listbox" :aria-label="t('Things to point at')">
          <li
            v-for="(thing, i) in suggestions"
            :id="optionId(i)"
            :key="thing.id"
            role="option"
            :aria-selected="i === active"
            :class="{ on: i === active }"
            @mousedown.prevent="pickOption(i)"
          ><span class="kind">{{ kindLabels[thing.kind] }}</span><span class="nm">{{ thing.name }}</span></li>
          <li
            v-if="offerNaming"
            :id="optionId(suggestions.length)"
            role="option"
            class="naming"
            :aria-selected="suggestions.length === active"
            :class="{ on: suggestions.length === active }"
            @mousedown.prevent="nameThem"
          >{{ t('Give names to {n} things without one', { n: unnamed }) }}</li>
        </ul>
        <p class="sr-only" role="status" aria-live="polite">{{ announceList }}</p>
        <ChatInput
          ref="input"
          v-model="draft"
          :name-of="(id) => session.nameOf(id)"
          :is-gone="(id) => session.isGone(id)"
          :placeholder="t('Message everyone, or @ai …')"
          :aria-label="t('chat message')"
          aria-autocomplete="list"
          aria-haspopup="listbox"
          aria-controls="tag-list"
          aria-describedby="pick-hint"
          :aria-expanded="listOpen"
          :aria-activedescendant="listOpen ? optionId(active) : undefined"
          @caret="caret = $event"
          @key="onChatKey"
          @submit="send"
          @focus="chatFocused = true"
          @blur="chatFocused = false"
        />
        <button class="send" type="submit" :aria-label="t('send')" :disabled="!draft.trim()">
          <svg viewBox="0 0 20 20" width="16" height="16"><path d="M4 10h11m-5-5 5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
        </button>
      </form>
      <p v-if="chatFocused" id="pick-hint" class="pick-hint">{{ t('Click something in the document to write a tag for it.') }}</p>
      <p v-else id="pick-hint" class="sr-only">{{ t('Click something in the document to write a tag for it.') }}</p>
    </section>
    </template>
    </div>

    <HelpPanel v-show="tab === 'help'" ref="helpPanel" class="helpTab" :session="session" />
    <ContextMenu v-if="menu" :x="menu.x" :y="menu.y" :items="menuItems" :label="t('Redaction menu')" :width="230" @close="menu = null" />
  </aside>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--ink);
  color: #e6e0f5;
}
.tabs {
  display: flex;
  flex: 0 0 auto;
  gap: 2px;
  padding: 8px 10px 0;
}
.tabs button {
  flex: 1;
  border: 0;
  border-radius: 8px 8px 0 0;
  padding: 7px 4px;
  background: transparent;
  color: rgb(230 224 245 / 60%);
  font: 500 11.5px var(--font-ui);
  letter-spacing: 0.02em;
  cursor: pointer;
}
.tabs button:hover {
  color: rgb(230 224 245 / 85%);
}
.tabs button.active {
  background: rgb(255 255 255 / 7%);
  color: #fff;
}
.historyChat {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
}
.helpTab {
  flex: 1 1 auto;
  min-height: 0;
}
section {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 0;
  padding: 12px 14px 10px;
}
section + section {
  border-top: 1px solid rgb(231 225 244 / 14%);
}
h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
  font: 500 11px var(--font-ui);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgb(230 224 245 / 62%);
}
.count {
  font-family: var(--font-mono);
  letter-spacing: 0;
}
ol {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow: auto;
  flex: 1;
  min-height: 0;
}
.viewerNote {
  margin: 0;
  padding: 14px 16px;
  color: rgb(230 224 245 / 80%);
  font: 400 13px/1.45 var(--font-ui);
}
.empty {
  color: rgb(230 224 245 / 55%);
  font-size: 12.5px;
  line-height: 1.5;
}
.empty b {
  color: #e6e0f5;
  font-weight: 500;
}
.log {
  font-size: 12px;
}
.entry {
  padding: 3px 0;
}
.entryRow {
  display: grid;
  grid-template-columns: 9px auto 1fr auto;
  align-items: baseline;
  gap: 8px;
  width: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
}
button.entryRow {
  cursor: pointer;
}
button.entryRow:hover .what {
  text-decoration: underline;
}
button.entryRow:focus-visible,
.visit:focus-visible,
.replayBtn:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}
/* The playhead: a marker that is not only a colour (BITV): a bar at the left and a heavier line. */
.entry.current,
.msg.current {
  box-shadow: inset 3px 0 0 var(--apricot);
  background: rgb(255 255 255 / 9%);
  padding-left: 6px;
}
.entry.later,
.entry.skipped,
.msg.skipped {
  opacity: 0.55;
}
.replayBtn {
  margin-left: auto;
  background: none;
  border: 1px solid rgb(231 225 244 / 30%);
  border-radius: 999px;
  color: rgb(230 224 245 / 85%);
  font: 500 10.5px var(--font-ui);
  letter-spacing: 0.02em;
  text-transform: none;
  padding: 2px 10px;
  cursor: pointer;
}
.replayBtn[aria-pressed='true'] {
  background: var(--iris);
  border-color: var(--iris);
  color: #fff;
}
.replayBtn:disabled {
  opacity: 0.45;
  cursor: default;
}
.replayBar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  margin: 0 0 8px;
  padding: 6px 8px;
  border-radius: 9px;
  background: rgb(255 255 255 / 6%);
  font-size: 11.5px;
}
.replayBar .segmented {
  flex: 0 0 auto;
}
.replayBar .segmented button {
  padding: 3px 9px;
  font-size: 11px;
}
.follow {
  display: flex;
  align-items: center;
  gap: 4px;
}
.where {
  font-family: var(--font-mono);
  color: rgb(230 224 245 / 75%);
}
.newer {
  color: var(--apricot);
}
.differs {
  color: rgb(230 224 245 / 85%);
}
.visit {
  margin-left: auto;
  background: none;
  border: 0;
  color: rgb(230 224 245 / 75%);
  font: 11px var(--font-ui);
  cursor: pointer;
}
.msg.current .visit {
  color: var(--apricot);
}
.entry .dot {
  align-self: center;
}
.who {
  color: rgb(230 224 245 / 70%);
}
.what {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.entry.undo .what {
  color: rgb(230 224 245 / 60%);
}
.entry em {
  font-style: normal;
  color: var(--apricot);
}
time {
  color: rgb(230 224 245 / 62%); /* 45% was 3.7:1 on the panel; 62% is 6:1 (BITV 1.4.3) */
  font-size: 11px;
}
/* what left the document (D1271): one muted line, not a change, so it has no dot and cannot be undone or redacted */
.left {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 2px 0;
  padding-left: 14px;
  color: rgb(230 224 245 / 62%);
  font-size: 11.5px;
  font-style: italic;
}
.left .who {
  font-style: normal;
}
.left time {
  margin-left: auto;
  font-style: normal;
}
.mark {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin: 6px 0;
  color: var(--apricot);
  font-size: 11.5px;
  border-top: 1px dashed rgb(242 160 87 / 40%);
  padding-top: 5px;
}
.mark .suggest {
  flex: 0 0 auto;
  background: none;
  border: 1px solid rgb(242 160 87 / 45%);
  border-radius: 999px;
  color: var(--apricot);
  font-size: 10.5px;
  padding: 1px 8px;
  cursor: pointer;
}
.mark .suggest:hover {
  background: rgb(242 160 87 / 14%);
}

/* -------------------------------------------------------------- picking what to redact, and what was (E3.14) */
.pickBar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  margin: 0 0 8px;
  padding: 6px 8px;
  border-radius: 9px;
  background: rgb(255 255 255 / 6%);
  font-size: 11.5px;
}
.pickBar .redactBtn {
  margin-left: auto;
  border: 0;
  border-radius: 999px;
  padding: 3px 10px;
  background: var(--rose);
  color: #fff;
  font: 600 11px var(--font-ui);
  cursor: pointer;
}
.pickBar .redactBtn:disabled {
  opacity: 0.45;
  cursor: default;
}
.pickBar .cancelPick {
  border: 0;
  background: none;
  color: rgb(230 224 245 / 80%);
  font: 11px var(--font-ui);
  text-decoration: underline;
  cursor: pointer;
}
.entry.picking {
  display: grid;
  grid-template-columns: 16px 1fr;
  align-items: baseline;
  gap: 4px;
}
.pick {
  margin: 0;
  accent-color: var(--iris);
}
/* What is picked: a bar at the left as well as the tint, not a colour alone (BITV). */
.entry.picked,
.msg.picked {
  box-shadow: inset 3px 0 0 var(--iris);
  background: rgb(91 75 196 / 22%);
}
.entry.redacted .what,
.entry.redacted .who {
  color: rgb(230 224 245 / 55%);
}
.dot.hatched {
  background: repeating-linear-gradient(45deg, rgb(230 224 245 / 70%) 0 1.5px, transparent 1.5px 3.5px);
  box-shadow: 0 0 0 1px rgb(230 224 245 / 45%);
}
.entry.record {
  color: rgb(230 224 245 / 85%);
}
.eraser {
  display: inline-flex;
  align-self: center;
  color: rgb(230 224 245 / 75%);
}
.msg.redacted p.gone {
  font-style: italic;
  color: rgb(230 224 245 / 60%);
  border: 1px dashed rgb(230 224 245 / 30%);
  border-radius: 8px;
  padding: 4px 8px;
}

/* -------------------------------------------------------------- the open suggestion to restore or switch (E3.7) */
.proposal {
  margin: 10px 14px 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--apricot) 16%, transparent);
  border: 1px solid color-mix(in srgb, var(--apricot) 40%, transparent);
  font-size: 12.5px;
}
.proposal .ask {
  margin: 0 0 8px;
  color: #fff;
}
.proposal .waiting {
  display: block;
  margin-top: 2px;
  color: rgb(230 224 245 / 65%);
  font-size: 11.5px;
}
.proposal .buttons {
  display: flex;
  gap: 6px;
}
.proposal button {
  border: 0;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 11.5px;
  cursor: pointer;
}
.proposal .agree {
  background: var(--iris);
  color: #fff;
}
.proposal .decline {
  background: rgb(255 255 255 / 10%);
  color: #fff;
}
.proposal .withdraw {
  background: none;
  color: rgb(230 224 245 / 75%);
  text-decoration: underline;
}

/* -------------------------------------------------------------------------------------------- lines (E3.8) */
.branches {
  flex: 0 0 auto;
  max-height: 160px;
}
.branches h2 {
  justify-content: space-between;
}
.branches .policy {
  margin-left: auto;
  background: rgb(255 255 255 / 8%);
  color: rgb(230 224 245 / 80%);
  border: 1px solid rgb(231 225 244 / 22%);
  border-radius: 999px;
  font-size: 10px;
  padding: 1px 6px;
}
.branchList {
  flex: 0 1 auto;
  overflow: auto;
}
.branch {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 3px 0;
  font-size: 12px;
}
.branch .name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
}
.branch:not(.active) .name {
  color: rgb(230 224 245 / 65%);
}
.branch .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--iris);
}
.branch .actions {
  display: flex;
  gap: 6px;
}
.branch .actions button {
  background: none;
  border: 1px solid rgb(231 225 244 / 22%);
  border-radius: 999px;
  color: rgb(230 224 245 / 80%);
  font-size: 10.5px;
  padding: 1px 8px;
  cursor: pointer;
}
.branch .actions button:hover {
  background: rgb(255 255 255 / 8%);
}
.peekBox {
  width: 100%;
  max-height: 90px;
  overflow: auto;
  margin: 4px 0 2px;
  padding: 6px 8px;
  background: rgb(0 0 0 / 25%);
  border-radius: 6px;
  font-size: 10.5px;
  color: rgb(230 224 245 / 80%);
  white-space: pre-wrap;
}
.discard {
  align-self: flex-start;
  margin-top: 6px;
  background: none;
  border: 1px solid rgb(231 225 244 / 22%);
  border-radius: 999px;
  color: rgb(230 224 245 / 65%);
  font-size: 10.5px;
  padding: 3px 10px;
  cursor: pointer;
}
.discard:hover {
  color: #fff;
  border-color: rgb(231 225 244 / 40%);
}
.messages {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.msg header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}
.author {
  font-size: 11px;
  font-weight: 500;
  padding: 1px 7px;
  border-radius: 999px;
}
.to {
  font-size: 11px;
  color: rgb(230 224 245 / 55%);
}
.msg p {
  margin: 0;
  font-size: 13px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.msg.ai p {
  background: color-mix(in srgb, var(--iris) 32%, transparent);
  border-radius: 4px 12px 12px 12px;
  padding: 7px 10px;
}
.typing {
  font-size: 12.5px;
  color: rgb(230 224 245 / 70%);
  display: flex;
  align-items: center;
  gap: 6px;
}
.dots {
  display: inline-flex;
  gap: 3px;
  margin-left: 2px;
}
.dots i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
  animation: blink 1.2s infinite both;
}
.dots i:nth-child(2) {
  animation-delay: 0.2s;
}
.dots i:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.2;
  }
  40% {
    opacity: 1;
  }
}
/* BITV 9.2.3.3 / WCAG 2.3.3: a person who asked their system for less motion gets still dots, not a pulse */
@media (prefers-reduced-motion: reduce) {
  .dots i {
    animation: none;
    opacity: 0.6;
  }
}
/* The panel is dark in both themes (`.panel`: --ink), so these use the panel's own light inks, not the page's
 * --text/--muted: with those the unchosen half was ink on ink, invisible in the light theme (owner's report). */
.aiMode {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  gap: 5px;
  padding: 10px 14px 4px;
  font-size: 11.5px;
  color: rgb(230 224 245 / 62%);
}
.segmented {
  display: flex;
  border: 1px solid rgb(231 225 244 / 28%);
  border-radius: 9px;
  overflow: hidden;
}
.segmented button {
  flex: 1;
  padding: 6px 4px;
  border: none;
  border-left: 1px solid rgb(231 225 244 / 28%);
  background: transparent;
  color: rgb(230 224 245 / 85%);
  font: 500 12px var(--font-ui);
  cursor: pointer;
}
.segmented button:first-child {
  border-left: none;
}
.segmented button:hover {
  background: rgb(255 255 255 / 7%);
  color: #fff;
}
.segmented button[aria-checked='true'] {
  background: var(--iris);
  color: #fff;
}
.segmented button:focus-visible {
  outline: 2px solid #fff;
  outline-offset: -3px;
}
.write {
  position: relative;
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.tagList {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 5;
  max-height: 220px;
  margin: 0;
  padding: 4px;
  border: 1px solid rgb(231 225 244 / 28%);
  border-radius: 10px;
  background: #2a2342;
  box-shadow: 0 8px 24px rgb(0 0 0 / 35%);
  overflow: auto;
  font-size: 12.5px;
}
.tagList li {
  display: flex;
  gap: 8px;
  align-items: baseline;
  padding: 5px 8px;
  border-radius: 6px;
  color: #e6e0f5;
  cursor: pointer;
}
.tagList li.on {
  background: var(--iris);
  color: #fff;
  box-shadow: inset 3px 0 0 var(--apricot); /* not only a colour (BITV) */
}
.tagList .kind {
  flex: 0 0 4.5em;
  color: rgb(230 224 245 / 70%);
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.tagList li.on .kind {
  color: rgb(255 255 255 / 85%);
}
.tagList .naming {
  margin-top: 2px;
  border-top: 1px dashed rgb(231 225 244 / 25%);
  border-radius: 0 0 6px 6px;
  color: var(--apricot);
}
.tag {
  display: inline;
  margin: 0 1px;
  padding: 0 6px;
  border: 1px solid rgb(231 225 244 / 40%);
  border-radius: 999px;
  background: rgb(255 255 255 / 10%);
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.tag:hover {
  background: rgb(255 255 255 / 18%);
}
.tag:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}
.tag.gone {
  text-decoration: line-through;
  border-style: dashed;
}
.pick-hint {
  margin: 4px 4px 0;
  font-size: 12px;
  color: rgb(230 224 245 / 70%);
}
.send {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 0;
  background: var(--iris);
  color: #fff;
  display: grid;
  place-items: center;
}
.send:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
