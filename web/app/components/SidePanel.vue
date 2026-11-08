<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { clock, colorOf, inkOn } from '~/lib/people'
import { useI18n } from '~/lib/i18n'
import type { BaseSession } from '~/lib/base-session'

const props = defineProps<{ session: BaseSession }>()
const state = props.session.state
// `t` stays this bare (never `i18n.t`): `scripts/extract_i18n.py`'s own regex only recognises an unqualified
// `t(...)` call (`obj.t(...)` is deliberately excluded, the same way `format(...)` is) -- see its docstring. Only
// the two static headers below need it; this panel has no Config ▸ App Language menu of its own.
const { t } = useI18n()

const history = ref<HTMLElement | null>(null)
const chatLog = ref<HTMLElement | null>(null)
const input = ref<HTMLInputElement | null>(null)
const draft = ref('')

/** The history with the checkpoints in their places. */
const rows = computed(() => {
  const marks = new Map<string, typeof state.checkpoints>()
  for (const c of state.checkpoints) marks.set(c.marks, [...(marks.get(c.marks) ?? []), c])
  const out: (
    | { kind: 'entry'; entry: (typeof state.entries)[number] }
    | { kind: 'mark'; label: string; author: string | null; number: number }
  )[] = []
  for (const entry of state.entries) {
    out.push({ kind: 'entry', entry })
    for (const c of marks.get(entry.revision) ?? []) out.push({ kind: 'mark', label: c.label || `checkpoint ${c.number}`, author: c.author, number: c.number })
  }
  return out
})

const others = computed(() => state.typing.filter((u) => u !== state.me.user))

// ------------------------------------------------------------------------------ lines, and restoring with consent (E3.7, E3.8)
const canWrite = computed(() => state.me.role === 'owner' || state.me.role === 'editor')
const isOwner = computed(() => state.me.role === 'owner')
const hiddenLines = computed(() => state.lines.filter((l) => !l.active))
const myProposal = computed(() => state.proposal)
const canWithdraw = computed(() => myProposal.value && (myProposal.value.by === state.me.user || isOwner.value))
const haveAgreed = computed(() => myProposal.value?.agreed.includes(state.me.user) ?? false)
const stillWaitingOn = computed(() => myProposal.value ? myProposal.value.group.filter((u) => !myProposal.value!.agreed.includes(u)) : [])

type Peeked = Exclude<Awaited<ReturnType<BaseSession['peekLine']>>, false>
const peeked = ref<Record<string, Peeked>>({})
async function togglePeek(line: string) {
  if (peeked.value[line]) {
    const { [line]: _drop, ...rest } = peeked.value
    peeked.value = rest
    return
  }
  const result = await props.session.peekLine(line)
  if (result) peeked.value = { ...peeked.value, [line]: result }
}

function suggestRestore(checkpoint: number) {
  void props.session.proposeRestore(checkpoint)
}
function suggestSwitch(line: string) {
  void props.session.proposeSwitch(line)
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
  const text = draft.value.trim()
  if (!text) return
  if (await props.session.say(text)) draft.value = ''
}

/** Tools ▸ Ask AI: put the cursor in the chat box, ready to write to the assistant. */
function ask(prefill = '@ai ') {
  draft.value = prefill
  nextTick(() => {
    input.value?.focus()
    input.value?.setSelectionRange(draft.value.length, draft.value.length)
  })
}
defineExpose({ ask })

const isAi = (user: string) => user.toLowerCase() === 'ai'
</script>

<template>
  <aside class="panel" aria-label="history and chat">
    <slot name="top" />

    <div v-if="myProposal" class="proposal" role="alert">
      <p class="ask">
        <b>{{ myProposal.by }}</b> suggests going to {{ myProposal.label }}.
        <span v-if="stillWaitingOn.length" class="waiting">Waiting on {{ stillWaitingOn.join(', ') }}.</span>
      </p>
      <div class="buttons">
        <button v-if="canWrite && !haveAgreed" type="button" class="agree" @click="agree">Agree</button>
        <button v-if="canWrite" type="button" class="decline" @click="decline">Decline</button>
        <button v-if="canWithdraw" type="button" class="withdraw" @click="withdraw">Withdraw</button>
      </div>
    </div>

    <section class="history">
      <h2>{{ t('History') }} <span class="count">{{ state.entries.length }}</span></h2>
      <ol ref="history" class="log mono" aria-label="everything that was done to this document">
        <li v-if="!rows.length" class="empty">Nothing yet. {{ { composes: 'Start writing.', creates: 'Put a text box on the slide.' }[state.app] ?? 'Type into a cell.' }}</li>
        <template v-for="(row, i) in rows" :key="i">
          <li v-if="row.kind === 'entry'" class="entry" :class="{ undo: row.entry.origin !== 'do' }">
            <span class="dot" :style="{ background: colorOf(state, row.entry.author ?? '') }" />
            <span class="who">{{ row.entry.author ?? '?' }}</span>
            <span class="what" :title="row.entry.label">
              <em v-if="row.entry.origin !== 'do'">{{ row.entry.origin }} · </em>{{ row.entry.summary }}
            </span>
            <time>{{ clock(row.entry.time) }}</time>
          </li>
          <li v-else class="mark">
            <span>◆ saved: {{ row.label }}<template v-if="row.author"> · {{ row.author }}</template></span>
            <button v-if="canWrite && !myProposal" type="button" class="suggest" title="Suggest going back to this checkpoint" @click="suggestRestore(row.number)">↺ restore</button>
          </li>
        </template>
      </ol>
    </section>

    <section class="lines" v-if="state.lines.length > 1 || hiddenLines.length">
      <h2>
        Lines <span class="count">{{ state.lines.length }}</span>
        <select v-if="isOwner" class="policy" :value="state.restorePolicy" title="What silence at a suggestion's deadline means" @change="setPolicy(($event.target as HTMLSelectElement).value as 'consensus' | 'veto')">
          <option value="consensus">silence = decline</option>
          <option value="veto">silence = agree</option>
        </select>
      </h2>
      <ol class="lineList">
        <li v-for="line in state.lines" :key="line.name" class="line" :class="{ active: line.active }">
          <span class="name"><span v-if="line.active" class="dot" />{{ line.name }}</span>
          <span class="actions">
            <button type="button" @click="togglePeek(line.name)">{{ peeked[line.name] ? 'close' : 'peek' }}</button>
            <button v-if="!line.active && canWrite && !myProposal" type="button" @click="suggestSwitch(line.name)">suggest switching here</button>
          </span>
          <pre v-if="peeked[line.name]" class="peekBox mono">{{ JSON.stringify(peeked[line.name]!.state, null, 1) }}</pre>
        </li>
      </ol>
      <button v-if="isOwner && hiddenLines.length && !myProposal" type="button" class="discard" @click="discard">Forget every hidden line</button>
    </section>

    <section class="chat">
      <h2>{{ t('Chat') }}</h2>
      <ol ref="chatLog" class="messages" aria-live="polite">
        <li v-if="!state.chat.length" class="empty">Write to everybody, or <b>@ai</b> to ask the assistant. Say <b>@ai help</b> to see what it can do.</li>
        <li
          v-for="m in state.chat"
          :key="m.number"
          class="msg"
          :class="{ ai: isAi(m.author), mine: m.author === state.me.user }"
        >
          <header>
            <span class="author" :style="{ background: colorOf(state, m.author), color: inkOn(colorOf(state, m.author)) }">{{ m.author }}</span>
            <span v-if="m.to" class="to">→ {{ m.to }}</span>
            <time>{{ clock(m.time) }}</time>
          </header>
          <p>{{ m.text }}</p>
        </li>
        <li v-if="others.length" class="typing">
          <span class="author" :style="{ background: colorOf(state, others[0]!), color: inkOn(colorOf(state, others[0]!)) }">{{ others[0] }}</span>
          is working<span class="dots"><i /><i /><i /></span>
        </li>
      </ol>
      <form class="write" @submit.prevent="send">
        <input
          ref="input"
          v-model="draft"
          aria-label="chat message"
          placeholder="Message everyone, or @ai …"
          autocomplete="off"
          maxlength="2000"
        />
        <button class="send" type="submit" aria-label="send" :disabled="!draft.trim()">
          <svg viewBox="0 0 20 20" width="16" height="16"><path d="M4 10h11m-5-5 5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
        </button>
      </form>
    </section>
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
  display: grid;
  grid-template-columns: 9px auto 1fr auto;
  align-items: baseline;
  gap: 8px;
  padding: 3px 0;
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
  color: rgb(230 224 245 / 45%);
  font-size: 11px;
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
.lines {
  flex: 0 0 auto;
  max-height: 160px;
}
.lines h2 {
  justify-content: space-between;
}
.lines .policy {
  margin-left: auto;
  background: rgb(255 255 255 / 8%);
  color: rgb(230 224 245 / 80%);
  border: 1px solid rgb(231 225 244 / 22%);
  border-radius: 999px;
  font-size: 10px;
  padding: 1px 6px;
}
.lineList {
  flex: 0 1 auto;
  overflow: auto;
}
.line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 3px 0;
  font-size: 12px;
}
.line .name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
}
.line:not(.active) .name {
  color: rgb(230 224 245 / 65%);
}
.line .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--iris);
}
.line .actions {
  display: flex;
  gap: 6px;
}
.line .actions button {
  background: none;
  border: 1px solid rgb(231 225 244 / 22%);
  border-radius: 999px;
  color: rgb(230 224 245 / 80%);
  font-size: 10.5px;
  padding: 1px 8px;
  cursor: pointer;
}
.line .actions button:hover {
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
.write {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.write input {
  flex: 1;
  min-width: 0;
  border-radius: 999px;
  border: 1px solid rgb(231 225 244 / 22%);
  background: rgb(255 255 255 / 6%);
  padding: 7px 14px;
  color: #fff;
}
.write input::placeholder {
  color: rgb(230 224 245 / 45%);
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
