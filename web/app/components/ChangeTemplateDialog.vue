<script setup lang="ts">
// Format ▸ Template ▸ Change Theme… and Change Template… (E10.4, E10.23, D1539, D1540; board
// `notes/mockups/creates-templates-new-and-server.svg`, panel M): give the presentation the look of a template of this
// server, or the whole template. "Theme only" gives the styles and the colours; "Theme and layouts" the layouts too,
// matched by name. What a presentation has of its own and the template has no match for stays. The server counts what
// the change would do, and the dialog says it before anything changes; one step, one Undo.
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import type { SlideSession } from '~/lib/slide-session'
import { resolveOrigin } from '~/lib/connection'
import { languageNow, useI18n } from '~/lib/i18n'
import { templateSummary, themeSummary, type ChangePreview } from '~/lib/template-change'
import { cardMeta, fetchTemplates, type TemplateCard } from '~/lib/templates'

const { t } = useI18n()

const props = defineProps<{ session: SlideSession; initial: 'theme' | 'layouts' }>()
const emit = defineEmits<{ close: [] }>()

const scope = ref<'theme' | 'layouts'>(props.initial)
const templates = ref<TemplateCard[]>([])
const chosen = ref('')
const preview = ref<ChangePreview | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')

const card = computed(() => templates.value.find((c) => c.id === chosen.value))
const lines = computed(() => (preview.value ? (scope.value === 'theme' ? themeSummary : templateSummary)(preview.value, t) : []))

onMounted(async () => {
  const origin = resolveOrigin(props.session.state.host, location.protocol, location.host)
  const found = await fetchTemplates(origin, languageNow())
  loading.value = false
  if ('error' in found) error.value = found.error
  else {
    templates.value = found.templates
    // The first template that was added, if there is one: the built-in one is what the presentation has anyway.
    chosen.value = (found.templates.find((c) => !c.builtin) ?? found.templates[0])?.id ?? ''
  }
})

/** The arrow keys move between the two scopes, as in any radio group: one tab stop, the other scope one key away. */
async function moveScope(event: KeyboardEvent) {
  scope.value = scope.value === 'theme' ? 'layouts' : 'theme'
  await nextTick()
  ;(event.currentTarget as HTMLElement).parentElement?.querySelector<HTMLElement>('[aria-checked=true]')?.focus()
}

let asked = 0
watch(chosen, async (id) => {
  preview.value = null
  if (!id) return
  const mine = ++asked
  const answer = await props.session.templateChangePreview(id)
  if (mine === asked && answer !== false) preview.value = answer // the answer to an earlier choice is of no use
})

async function change() {
  if (!chosen.value) return
  busy.value = true
  error.value = ''
  const answer = scope.value === 'theme' ? await props.session.changeTheme(chosen.value) : await props.session.changeTemplate(chosen.value)
  busy.value = false
  if (answer === false) return // the session has said why
  if (!answer.changed) props.session.notice(t('The presentation looks like this already: nothing changed.'))
  emit('close')
}
</script>

<template>
  <Modal :title="scope === 'theme' ? t('Change theme') : t('Change template')" :width="640" @close="emit('close')">
    <p v-if="loading" class="hint" role="status">{{ t('Loading…') }}</p>
    <form v-else @submit.prevent="change">
      <div class="scopes" role="radiogroup" :aria-label="t('What to change')">
        <button type="button" role="radio" class="scope" :class="{ on: scope === 'theme' }" :aria-checked="scope === 'theme'" :tabindex="scope === 'theme' ? 0 : -1" @click="scope = 'theme'" @keydown.arrow-right.arrow-left.arrow-down.arrow-up.prevent="moveScope">{{ t('Theme only') }}</button>
        <button type="button" role="radio" class="scope" :class="{ on: scope === 'layouts' }" :aria-checked="scope === 'layouts'" :tabindex="scope === 'layouts' ? 0 : -1" @click="scope = 'layouts'" @keydown.arrow-right.arrow-left.arrow-down.arrow-up.prevent="moveScope">{{ t('Theme and layouts') }}</button>
      </div>
      <label class="field">
        {{ t('Template') }}
        <select v-model="chosen">
          <option v-for="c in templates" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </label>
      <p v-if="card" class="hint">{{ card.purpose }} · {{ cardMeta(card, t) }}</p>
      <dl v-if="lines.length" class="summary">
        <template v-for="line in lines" :key="line.heading">
          <dt>{{ line.heading }}</dt>
          <dd>{{ line.text }}</dd>
        </template>
      </dl>
      <p class="hint">{{ t('What your presentation has and the template has no match for stays as it is. One Undo takes it all back.') }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="busy || !chosen || !preview">{{ scope === 'theme' ? t('Change theme') : t('Change template') }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.scopes {
  display: inline-flex;
  margin: 0 0 12px;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  overflow: hidden;
}
.scope {
  border: none;
  background: var(--surface);
  color: var(--text);
  padding: 7px 16px;
  font: 13.5px var(--font-ui);
  cursor: pointer;
}
.scope.on {
  background: var(--ink);
  color: var(--paper);
}
.summary {
  margin: 12px 0;
}
dt {
  margin-top: 8px;
  font: 600 13.5px var(--font-ui);
}
dd {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--muted);
}
.hint {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: var(--muted);
}
.error {
  margin: 8px 0 0;
  font-size: 13px;
  color: color-mix(in srgb, var(--rose) 72%, var(--text));
}
.buttons {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
