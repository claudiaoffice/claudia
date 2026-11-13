<script setup lang="ts">
// The toolbar row of a text: the style of the paragraph (you mark text by what it is for, D62) and how to look at the text.
import { ref } from 'vue'
import { colorOf } from '~/lib/people'
import type { TextSession } from '~/lib/text-session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ session: TextSession; view: 'flow' | 'page'; authors: boolean }>()
const emit = defineEmits<{ view: [view: 'flow' | 'page']; authors: [on: boolean]; styled: []; look: [at: { x: number; y: number }] }>()

const state = props.session.state
// The list is a floating panel at the button, not a child of the bar: the bar scrolls sideways on a narrow window, which
// would clip anything that hangs out of it.
const at = ref<{ x: number; y: number } | null>(null)
const button = ref<HTMLElement | null>(null)
const look = ref<HTMLElement | null>(null)

const below = (el: HTMLElement | null) => {
  const r = el?.getBoundingClientRect()
  return { x: r?.left ?? 0, y: (r?.bottom ?? 0) + 4 }
}

function toggle() {
  at.value = at.value ? null : below(button.value)
}

function close() {
  at.value = null
}

const current = () => state.styles.find((s) => s.id === props.session.currentStyle()) ?? state.styles[0]

function choose(id: string) {
  close()
  void props.session.setStyle(id)
  emit('styled')
}

// -- lists (E9.21): the same things as Format ▸ List, within reach of the hand that is typing
const kind = () => props.session.currentScheme()
function list(scheme: 'bullets' | 'numbers') {
  void props.session.makeList(scheme)
  emit('styled')
}
function nest(by: 1 | -1) {
  void props.session.indent(by)
  emit('styled')
}

const writers = () => [state.me.user, ...state.people.map((p) => p.user)].filter((u, i, all) => all.indexOf(u) === i)
</script>

<template>
  <div class="stylebar" role="toolbar" :aria-label="t('Text')">
    <div class="style-picker">
      <button
        ref="button"
        class="style-btn"
        type="button"
        aria-haspopup="listbox"
        :aria-expanded="!!at"
        :disabled="session.readOnly"
        :title="t('Style: mark text by what it is for')"
        data-testid="style-button"
        @mousedown.prevent
        @click="toggle"
      >
        <span>{{ current()?.name ?? 'Body text' }}</span
        ><span class="caret">▾</span>
      </button>
      <Popover v-if="at" :x="at.x" :y="at.y" :width="300" :anchor="button" :label="t('Styles')" @close="close">
        <ul class="style-list" role="listbox" :aria-label="t('Styles')">
          <li v-for="s in state.styles" :key="s.id" role="option" :aria-selected="s.id === current()?.id">
            <button class="style-opt" :class="{ current: s.id === current()?.id }" type="button" :data-style="s.id" @click="choose(s.id)">
              <span class="name">{{ s.name }}</span
              ><span class="purpose">{{ s.purpose }}</span>
            </button>
          </li>
        </ul>
      </Popover>
    </div>
    <button ref="look" class="tool" type="button" :disabled="session.readOnly" :title="t('How this style looks: font, size, colour, CSS (right-click in the text does the same)')" data-testid="look-button" @mousedown.prevent @click="emit('look', below(look))">{{ t('Look…') }}</button>

    <div class="segmented" role="group" :aria-label="t('List')">
      <button type="button" :aria-pressed="kind() === 'bullets'" :disabled="session.readOnly" :title="t('Bulleted list (Ctrl+Shift+8)')" data-testid="list-bullets" @mousedown.prevent @click="list('bullets')">
        <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><g fill="currentColor"><circle cx="2.5" cy="4" r="1.3" /><circle cx="2.5" cy="8" r="1.3" /><circle cx="2.5" cy="12" r="1.3" /></g><path d="M6 4h8M6 8h8M6 12h8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" fill="none" /></svg>
        <span class="sr">{{ t('Bulleted list') }}</span>
      </button>
      <button type="button" :aria-pressed="kind() === 'numbers'" :disabled="session.readOnly" :title="t('Numbered list (Ctrl+Shift+7)')" data-testid="list-numbers" @mousedown.prevent @click="list('numbers')">
        <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><g fill="currentColor" font-size="5" font-family="sans-serif" font-weight="700"><text x="0.5" y="5.2">1</text><text x="0.5" y="9.2">2</text><text x="0.5" y="13.2">3</text></g><path d="M6 4h8M6 8h8M6 12h8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" fill="none" /></svg>
        <span class="sr">{{ t('Numbered list') }}</span>
      </button>
    </div>
    <button class="tool icon" type="button" :disabled="session.readOnly || !session.currentItem()" :title="t('Outdent (Shift+Tab)')" data-testid="list-outdent" @mousedown.prevent @click="nest(-1)">
      <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M2 3h12M7 7h7M7 11h7M2 15h12M5 7.5 2.5 9 5 10.5Z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(0 -1.5)" /></svg>
      <span class="sr">{{ t('Outdent') }}</span>
    </button>
    <button class="tool icon" type="button" :disabled="session.readOnly || !session.currentItem()" :title="t('Indent (Tab)')" data-testid="list-indent" @mousedown.prevent @click="nest(1)">
      <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M2 3h12M7 7h7M7 11h7M2 15h12M2.5 7.5 5 9 2.5 10.5Z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(0 -1.5)" /></svg>
      <span class="sr">{{ t('Indent') }}</span>
    </button>

    <span class="grow" />

    <span v-if="authors" class="legend" :aria-label="t('authorship colours')">
      <span v-for="user in writers()" :key="user" :style="{ '--c': colorOf(state, user) }"><i />{{ user }}</span>
    </span>
    <button class="tool" :class="{ on: authors }" type="button" :aria-pressed="authors" :title="t('Show Who Wrote What')" data-testid="authors" @mousedown.prevent @click="emit('authors', !authors)">{{ t('Authors') }}</button>
    <div class="segmented" role="group" :aria-label="t('View')">
      <button type="button" :aria-pressed="view === 'flow'" :title="t('Flow: the text runs to the width of the window')" @mousedown.prevent @click="emit('view', 'flow')">{{ t('Flow') }}</button>
      <button type="button" :aria-pressed="view === 'page'" :title="t('Page: the text on a page')" data-testid="page-view" @mousedown.prevent @click="emit('view', 'page')">{{ t('Page') }}</button>
    </div>
  </div>
</template>

<style scoped>
.stylebar {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 44px;
  padding: 0 14px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  overflow-x: auto;
  scrollbar-width: none;
}
.stylebar > * {
  flex-shrink: 0;
}
.grow {
  flex: 1;
}
.tool {
  height: 30px;
  padding: 0 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  font-weight: 500;
}
.tool.icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  padding: 0;
}
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.segmented button svg {
  display: block;
}
.segmented button:disabled {
  opacity: 0.5;
}
.tool:disabled {
  opacity: 0.5;
}
.tool:hover:not(:disabled) {
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode */
}
.tool.on {
  background: color-mix(in srgb, var(--app) 16%, transparent);
  color: var(--app-text); /* --app-dark as literal text fails contrast in dark mode — the owner's 2026-11-06 report */
}
.style-picker {
  position: relative;
}
.style-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 190px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
  background: var(--surface);
  font-weight: 500;
}
.style-btn:hover:not(:disabled) {
  border-color: var(--app);
}
.style-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.caret {
  color: var(--muted);
  font-size: 10px;
}
.style-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.style-opt {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 7px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  text-align: left;
}
.style-opt:hover {
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode */
}
.style-opt.current {
  background: color-mix(in srgb, var(--app) 14%, transparent);
}
.name {
  font-weight: 500;
}
.purpose {
  color: var(--muted);
  font-size: 12px;
}
.segmented {
  display: inline-flex;
  padding: 2px;
  border-radius: 9px;
  background: var(--mist);
}
.segmented button {
  height: 26px;
  padding: 0 12px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  font-weight: 500;
  font-size: 13px;
  color: var(--muted);
}
.segmented button[aria-pressed='true'] {
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 1px 2px rgb(31 26 51 / 14%);
}
.legend {
  display: inline-flex;
  gap: 10px;
  margin-right: 6px;
  font-size: 12px;
  color: var(--muted);
}
.legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.legend i {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  background: var(--c);
}
</style>
