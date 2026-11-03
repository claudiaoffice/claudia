<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { clock, colorOf, inkOn } from '~/lib/people'
import type { BaseSession } from '~/lib/base-session'

const props = defineProps<{ session: BaseSession }>()
const state = props.session.state

const history = ref<HTMLElement | null>(null)
const chatLog = ref<HTMLElement | null>(null)
const input = ref<HTMLInputElement | null>(null)
const draft = ref('')

/** The history with the checkpoints in their places. */
const rows = computed(() => {
  const marks = new Map<string, typeof state.checkpoints>()
  for (const c of state.checkpoints) marks.set(c.marks, [...(marks.get(c.marks) ?? []), c])
  const out: ({ kind: 'entry'; entry: (typeof state.entries)[number] } | { kind: 'mark'; label: string; author: string | null })[] = []
  for (const entry of state.entries) {
    out.push({ kind: 'entry', entry })
    for (const c of marks.get(entry.revision) ?? []) out.push({ kind: 'mark', label: c.label || `checkpoint ${c.number}`, author: c.author })
  }
  return out
})

const others = computed(() => state.typing.filter((u) => u !== state.me.user))

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
    <section class="history">
      <h2>History <span class="count">{{ state.entries.length }}</span></h2>
      <ol ref="history" class="log mono" aria-label="everything that was done to this document">
        <li v-if="!rows.length" class="empty">Nothing yet. {{ state.app === 'composes' ? 'Start writing.' : 'Type into a cell.' }}</li>
        <template v-for="(row, i) in rows" :key="i">
          <li v-if="row.kind === 'entry'" class="entry" :class="{ undo: row.entry.origin !== 'do' }">
            <span class="dot" :style="{ background: colorOf(state, row.entry.author ?? '') }" />
            <span class="who">{{ row.entry.author ?? '?' }}</span>
            <span class="what" :title="row.entry.label">
              <em v-if="row.entry.origin !== 'do'">{{ row.entry.origin }} · </em>{{ row.entry.summary }}
            </span>
            <time>{{ clock(row.entry.time) }}</time>
          </li>
          <li v-else class="mark"><span>◆ saved: {{ row.label }}<template v-if="row.author"> · {{ row.author }}</template></span></li>
        </template>
      </ol>
    </section>

    <section class="chat">
      <h2>Chat</h2>
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
  margin: 6px 0;
  color: var(--apricot);
  font-size: 11.5px;
  border-top: 1px dashed rgb(242 160 87 / 40%);
  padding-top: 5px;
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
