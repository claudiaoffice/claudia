<script setup lang="ts">
// The two optional fields about a document: its description (Markdown, with a preview) and its tags (chips, typed with
// Enter or a comma, suggested from what the place already uses so that "finance" does not drift into "finances").
// Shared by the import dialog and Details… so they look and work the same (sheet 10, UX consistency). Both are public
// by design (D103): the note under the description says so every time. `fromFile` says where a starting value came from.
import { computed, ref } from 'vue'
import { MAX_DESCRIPTION, MAX_TAGS, addTags, tagChoices } from '~/lib/open'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  /** The place's tags and how often they are used, for suggestions. */
  counts: { tag: string; count: number }[]
  /** The place in the sidebar's words ("Private on this computer"). */
  place: string
  readonly?: boolean
  /** The start values came from the file: "from the file: Comments". */
  descriptionFromFile?: boolean
  tagsFromFile?: boolean
  /** The ids that make the fields unique when two sets are on a page. */
  idPrefix?: string
}>()
const description = defineModel<string>('description', { default: '' })
const tags = defineModel<string[]>('tags', { default: () => [] })

const previewing = ref(false)
const typed = ref('')
const focused = ref(false)
const input = ref<HTMLInputElement | null>(null)
const problem = ref('')
const prefix = props.idPrefix ?? 'details'

const choices = computed(() => tagChoices(props.counts, typed.value, tags.value).slice(0, 6))
const showChoices = computed(() => focused.value && !props.readonly && (choices.value.length > 0 || typed.value.trim() !== ''))

/** Take what was typed as tags (it may hold several, split by commas). */
function commit() {
  const added = addTags(tags.value, typed.value)
  typed.value = ''
  problem.value = added.problem
  if (added.tags.length !== tags.value.length) tags.value = added.tags
}
function take(tag: string) {
  typed.value = tag
  commit()
  input.value?.focus()
}
function remove(tag: string) {
  tags.value = tags.value.filter((x) => x !== tag)
}
function onKey(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ',') {
    if (typed.value.trim() === '' && event.key === 'Enter') return // an empty Enter submits the form as usual
    event.preventDefault()
    commit()
  } else if (event.key === 'Backspace' && typed.value === '' && tags.value.length) {
    tags.value = tags.value.slice(0, -1)
  }
}
</script>

<template>
  <div class="fields">
    <div class="field">
      <div class="head">
        <label :for="`${prefix}-description`">{{ t('Description') }} <span class="optional">({{ t('optional') }})</span></label>
        <span class="tabs" role="group" :aria-label="t('Description view')">
          <button type="button" class="link" :aria-pressed="!previewing" @click="previewing = false">{{ t('Write') }}</button>
          <button type="button" class="link" :aria-pressed="previewing" @click="previewing = true">{{ t('Preview') }}</button>
        </span>
      </div>
      <NotesText v-if="previewing" class="preview" :notes="description || t('Nothing to preview yet.')" />
      <textarea
        v-else
        :id="`${prefix}-description`"
        v-model="description"
        rows="4"
        :maxlength="MAX_DESCRIPTION"
        :readonly="readonly"
        :placeholder="t('What is this document for? Others see this in the list.')"
        :aria-describedby="`${prefix}-public`"
      />
      <p v-if="descriptionFromFile" class="from">{{ t('from the file') }} · {{ t('Change it as you like.') }}</p>
      <p :id="`${prefix}-public`" class="hint">{{ t('Markdown. Shown in the list to everybody who can see {place}, also without a password.', { place }) }}</p>
    </div>

    <div class="field">
      <label :for="`${prefix}-tag`">{{ t('Tags') }} <span class="optional">({{ t('optional') }})</span></label>
      <div class="tagbox" :class="{ readonly }" @click="input?.focus()">
        <span v-for="tag in tags" :key="tag" class="chip">
          {{ tag }}
          <button v-if="!readonly" type="button" :aria-label="t('Remove tag {tag}', { tag })" @click.stop="remove(tag)">×</button>
        </span>
        <input
          v-if="!readonly"
          :id="`${prefix}-tag`"
          ref="input"
          v-model="typed"
          autocomplete="off"
          :placeholder="tags.length ? t('Add a tag…') : t('Add tags, e.g. finance, 2027')"
          :aria-describedby="`${prefix}-tag-hint`"
          @keydown="onKey"
          @focus="focused = true"
          @blur="commit(); focused = false"
        >
      </div>
      <ul v-if="showChoices" class="choices" :aria-label="t('Already used on {place}', { place })">
        <li v-for="c in choices" :key="c.tag">
          <button type="button" @mousedown.prevent="take(c.tag)">{{ c.tag }} <span class="count">{{ t('{count} docs', { count: c.count }) }}</span></button>
        </li>
        <li v-if="typed.trim() && !choices.some((c) => c.tag === typed.trim().toLowerCase())">
          <button type="button" @mousedown.prevent="commit()">{{ t('Add “{tag}” as a new tag', { tag: typed.trim() }) }}</button>
        </li>
      </ul>
      <p v-if="tagsFromFile" class="from">{{ t('from the file') }}</p>
      <p v-if="problem" class="error" role="alert">{{ problem }}</p>
      <p :id="`${prefix}-tag-hint`" class="hint">{{ t('Type, then Enter or comma. At most {count} tags.', { count: MAX_TAGS }) }}</p>
    </div>
  </div>
</template>

<style scoped>
.fields {
  display: grid;
  gap: 14px;
}
.field {
  display: grid;
  gap: 4px;
  position: relative;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.optional {
  color: var(--muted);
  font-size: 12px;
}
.tabs {
  display: flex;
  gap: 10px;
}
.tabs .link[aria-pressed='true'] {
  font-weight: 600;
  text-decoration: underline;
}
textarea {
  width: 100%;
  resize: vertical;
  font: 13px/1.4 var(--mono, ui-monospace, monospace);
  border: 1px solid var(--line-field);
  border-radius: 9px;
  padding: 8px 10px;
  background: transparent;
  color: var(--text);
}
.preview {
  min-height: 5.6em;
  border: 1px solid var(--line-field);
  border-radius: 9px;
  padding: 8px 10px;
  background: var(--app-soft);
}
.hint {
  color: var(--muted);
  font-size: 12px;
  margin: 0;
}
.from {
  margin: 0;
  font-size: 12px;
  color: var(--app-text);
}
.error {
  color: var(--rose);
  margin: 0;
  font-size: 12px;
}
.tagbox {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  border: 1px solid var(--line-field);
  border-radius: 9px;
  padding: 4px 8px;
  min-height: 36px;
}
.tagbox input {
  flex: 1 1 8em;
  min-width: 6em;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--text);
}
.tagbox:focus-within {
  border-color: var(--app);
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 999px;
  background: var(--app-soft);
  padding: 1px 4px 1px 10px;
  font-size: 12.5px;
}
.chip button {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0 4px;
}
.readonly .chip {
  padding-right: 10px;
}
.choices {
  list-style: none;
  margin: 0;
  padding: 4px;
  display: grid;
  gap: 2px;
  border: 1px solid var(--line-field);
  border-radius: 10px;
  background: var(--surface);
  box-shadow: var(--shadow);
}
.choices button {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  border: 0;
  background: transparent;
  color: var(--text);
  font: 13px var(--font-ui);
  padding: 5px 8px;
  border-radius: 7px;
  text-align: left;
  cursor: pointer;
}
.choices button:hover,
.choices button:focus-visible {
  background: var(--app-soft);
}
.count {
  color: var(--muted);
  font-size: 12px;
}
</style>
