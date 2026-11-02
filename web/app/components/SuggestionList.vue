<script setup lang="ts">
// What the assistant suggests (D63): each suggestion says what it would change and why. Nothing is written until a
// person accepts; the accepter is the author of the new text, and the suggestion's author is remembered with it.
import { computed } from 'vue'
import type { TextSession } from '~/lib/text-session'

const props = defineProps<{ session: TextSession; active: string | null }>()
const emit = defineEmits<{ pick: [id: string] }>()

const state = props.session.state
const items = computed(() => state.suggestions.filter((s) => s.state === 'open'))
</script>

<template>
  <section class="suggestions" aria-label="suggestions" data-testid="suggestions">
    <h2>Suggestions <span class="count">{{ items.length }}</span></h2>
    <p v-if="!items.length" class="empty">None. Ask <b>@ai review this text</b> and it will suggest changes; nothing is written until you accept.</p>
    <ul v-else>
      <li v-for="s in items" :key="s.id" :class="{ hot: s.id === active, outdated: s.outdated }" :data-suggestion="s.id" @click="emit('pick', s.id)">
        <p class="reason">{{ s.reason }}</p>
        <p v-if="s.replacement !== null" class="change">
          <del>{{ s.original || '·' }}</del> <span class="arrow">→</span> <ins>{{ s.replacement || '(delete)' }}</ins>
        </p>
        <p v-else class="change remark">“{{ s.original.length > 60 ? s.original.slice(0, 60) + '…' : s.original }}”</p>
        <p v-if="s.outdated" class="note">The text under it changed. It cannot be accepted any more.</p>
        <div class="buttons">
          <button v-if="s.replacement !== null" type="button" class="accept" :disabled="s.outdated || session.readOnly" @click.stop="session.accept(s.id)">Accept</button>
          <button type="button" class="reject" :disabled="session.readOnly" @click.stop="session.reject(s.id)">{{ s.replacement === null ? 'Dismiss' : 'Reject' }}</button>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.suggestions {
  flex: 0 1 auto;
  max-height: 46%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 12px 14px 10px;
  border-bottom: 1px solid rgb(231 225 244 / 14%);
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
.empty {
  margin: 0;
  color: rgb(230 224 245 / 55%);
  font-size: 13px;
}
ul {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow: auto;
  display: grid;
  gap: 8px;
}
li {
  padding: 9px 10px;
  border-radius: 9px;
  background: rgb(231 225 244 / 8%);
  border: 1px solid transparent;
  cursor: pointer;
}
li.hot {
  border-color: rgb(231 225 244 / 55%);
}
li.outdated {
  opacity: 0.7;
}
p {
  margin: 0;
}
.reason {
  font-size: 12.5px;
  color: rgb(230 224 245 / 82%);
}
.change {
  margin-top: 5px;
  font-size: 14px;
}
del {
  text-decoration-color: #b8a9ff;
  color: rgb(230 224 245 / 70%);
}
ins {
  text-decoration: none;
  font-weight: 600;
  color: #fff;
}
.arrow {
  color: rgb(230 224 245 / 50%);
}
.remark {
  font-style: italic;
  color: rgb(230 224 245 / 75%);
}
.note {
  margin-top: 4px;
  font-size: 12px;
  color: var(--apricot);
}
.buttons {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
button {
  border: 1px solid rgb(231 225 244 / 30%);
  background: transparent;
  color: #e6e0f5;
  border-radius: 999px;
  padding: 3px 12px;
  font-size: 12.5px;
  font-weight: 500;
}
button:hover:not(:disabled) {
  background: rgb(231 225 244 / 14%);
}
button.accept {
  background: var(--app);
  border-color: var(--app);
  color: #fff;
}
button.accept:hover:not(:disabled) {
  background: var(--app-dark);
}
button:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
