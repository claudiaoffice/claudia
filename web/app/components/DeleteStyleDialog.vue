<script setup lang="ts">
// Delete the style “…”? (E1.10, D226, D785, `style-delete-and-hide.svg` panels B and C): what the deletion does is said in
// words before anything happens, and the person chooses between two ways. Assigning another style is the first and
// preselected, with the plain style of the kind on it — that is what "no style" means where everything has one — and
// it is the only way that changes looks, which it counts first. Re-basing keeps every look and builds it on a style
// of the person's choice; the styles that could not keep the look are named with the server's reason.
// The wording and the state are in `lib/style-deletion.ts`, where they are tested.
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from '~/lib/i18n'
import type { StyleHost } from '~/lib/style-host'
import type { StyleView } from '~/lib/style-css'
import {
  DeletionChoice,
  basedOnLine,
  lookDifference,
  lookDifferentLine,
  lookLostLine,
  usedByLine,
  wasRefused,
  type DeleteHow,
  type StyleDeletion,
} from '~/lib/style-deletion'

const { t } = useI18n()
const props = defineProps<{ host: StyleHost; style: StyleView }>()
const emit = defineEmits<{ close: []; deleted: [done: { name: string; how: DeleteHow; standIn: string | null; target: string | undefined }] }>()

const choice = ref<DeletionChoice | null>(null)
const failed = ref(false)
const refused = ref('')
const busy = ref(false)

onMounted(async () => {
  const found = await props.host.deletion?.preview(props.style.id)
  // A protected style is never offered Delete…, so this is a server that said otherwise: nothing to ask.
  if (!found || found.protected) failed.value = true
  else choice.value = reactive(new DeletionChoice(found)) as DeletionChoice
})

const noun = computed(() => props.host.usesNoun ?? props.host.noun)
const deletion = computed<StyleDeletion | null>(() => choice.value?.deletion ?? null)
const byId = (id: string | undefined) => (id ? props.host.styles.find((s) => s.id === id) : undefined)
const assigned = computed(() => choice.value?.target('assign'))
const rebased = computed(() => choice.value?.target('rebase'))
const assignedView = computed(() => byId(assigned.value?.id))
/** What the style says itself, in words: what stays when it is re-based. */
const ownSettings = computed(() => lookDifference({}, props.style.css).join(', '))
const cannotHold = computed(() => deletion.value?.targets.filter((x) => !x.holds) ?? [])
const plain = computed(() => !!assigned.value && assigned.value.id === deletion.value?.suggested?.id)

function pickFrom(how: DeleteHow, event: Event) {
  choice.value?.pick(how, (event.target as HTMLSelectElement).value || null)
  refused.value = ''
}
function chooseHow(how: DeleteHow) {
  if (choice.value) choice.value.how = how
  refused.value = ''
}

async function remove() {
  const c = choice.value
  if (!c || !c.ready || busy.value || !props.host.deletion) return
  busy.value = true
  refused.value = ''
  const { how, target } = c.request
  const done = await props.host.deletion.remove(props.style.id, how, target)
  busy.value = false
  if (!done) return
  if (wasRefused(done)) {
    refused.value = done.refused
    return
  }
  emit('deleted', { name: props.style.name, how, standIn: done.standIn, target: byId(target ?? undefined)?.name })
  emit('close')
}
</script>

<template>
  <Modal :title="t('Delete the style “{name}”?', { name: style.name })" :width="620" @close="emit('close')">
    <p v-if="failed" class="line" role="alert">{{ t('This document cannot say what deleting the style would do.') }}</p>
    <p v-else-if="!choice || !deletion" class="line">{{ t('Looking up what deleting it does…') }}</p>
    <form v-else class="ask" data-testid="style-delete" @submit.prevent="remove">
      <div class="facts">
        <p class="line">{{ usedByLine(noun, deletion) }}</p>
        <p v-if="deletion.children.length" class="line">{{ basedOnLine(deletion) }}</p>
      </div>

      <fieldset v-if="choice.needsTarget" class="ways">
        <legend class="sr">{{ t('How to delete the style') }}</legend>

        <div class="way" :class="{ on: choice.how === 'assign' }">
          <label class="head">
            <input type="radio" name="how" value="assign" :checked="choice.how === 'assign'" data-testid="way-assign" @change="chooseHow('assign')" >
            <span>{{ t('Assign another style') }}</span>
          </label>
          <p class="say">{{ t('Everything that has “{name}” gets the style you choose instead, and looks like it. What is based on “{name}” is based on that style too, and loses what “{name}” said.', { name: style.name }) }}</p>
          <select :value="assigned?.id ?? ''" :aria-label="t('Style to assign')" data-testid="assign-target" @change="pickFrom('assign', $event)">
            <option value="" disabled>{{ t('Choose a style…') }}</option>
            <option v-for="x in deletion.targets" :key="x.id" :value="x.id">{{ x.name }}</option>
          </select>
          <p v-if="plain && assigned" class="say">{{ t('“{name}” is what “no style” means here: the plain one of its kind.', { name: assigned.name }) }}</p>
          <p v-if="choice.how === 'assign' && choice.looksChange" class="change" data-testid="looks-change">
            <span>{{ lookDifferentLine(noun, deletion) }}</span>
            <span v-if="lookLostLine(style, assignedView)">{{ lookLostLine(style, assignedView) }}</span>
          </p>
        </div>

        <div class="way" :class="{ on: choice.how === 'rebase' }">
          <label class="head">
            <input type="radio" name="how" value="rebase" :checked="choice.how === 'rebase'" data-testid="way-rebase" @change="chooseHow('rebase')" >
            <span>{{ t('Re-base on another style') }}</span>
          </label>
          <p class="say">{{ t('Everything that has “{name}” keeps looking exactly as it does now, but is built on the style you choose: it follows that style from now on, except where “{name}” differed. What had “{name}” itself moves to a new style, “{name} (kept)”, that waits for a name.', { name: style.name }) }}</p>
          <select :value="rebased?.id ?? ''" :aria-label="t('Style to re-base on')" data-testid="rebase-target" @change="pickFrom('rebase', $event)">
            <option value="" disabled>{{ t('Choose a style…') }}</option>
            <option v-for="x in deletion.targets" :key="x.id" :value="x.id" :disabled="!x.holds">{{ x.name }}</option>
          </select>
          <p v-if="rebased && ownSettings" class="say">{{ t('“{name}” sets {what} itself, and that stays. Everything else follows “{target}”, now and whenever it changes.', { name: style.name, what: ownSettings, target: rebased.name }) }}</p>
          <div v-if="cannotHold.length" class="say" data-testid="cannot-hold">
            <p>{{ t('These styles cannot be chosen, because the look could not be kept under them:') }}</p>
            <ul>
              <li v-for="x in cannotHold" :key="x.id"><strong>{{ x.name }}</strong>: {{ x.reason }}</li>
            </ul>
          </div>
        </div>
      </fieldset>
      <p v-else class="say">{{ t('Nothing has this style and nothing is based on it, so it just goes.') }}</p>

      <p v-if="refused" class="refused" role="alert" data-testid="refused">{{ refused }}</p>

      <div class="foot">
        <span class="say">{{ t('One step in the history. Undo puts everything back.') }}</span>
        <span class="buttons">
          <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
          <button class="btn danger" type="submit" :disabled="!choice.ready || busy" data-testid="delete-style">{{ t('Delete style') }}</button>
        </span>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.ask {
  display: grid;
  gap: 14px;
}
.facts {
  display: grid;
  gap: 2px;
}
.line,
.say {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
}
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.ways {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  border: 0;
  min-width: 0;
}
.way {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 10px;
}
.way.on {
  border-color: var(--app);
}
.head {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
}
.way select {
  justify-self: start;
  min-width: 220px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
}
.way ul {
  margin: 4px 0 0;
  padding-left: 18px;
}
/* Amber on the surface passes 4.5:1 in both themes: the text colour is the theme's own, only the rule beside it is amber. */
.change {
  /* the count, and under it what differs: two lines, not one run-on sentence */
  margin: 0;
  padding-left: 10px;
  border-left: 3px solid var(--apricot);
  font-size: 13px;
  font-weight: 600;
}
.refused {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--danger, #c01c28);
  font-size: 13px;
}
.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.buttons {
  display: inline-flex;
  gap: 10px;
}
.change span { display: block; }
</style>
