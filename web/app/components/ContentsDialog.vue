<script setup lang="ts">
// The options of a table of contents (E9.31, `composes-table-of-contents.svg`, C), and in creates of an agenda: the
// levels it lists, numbers, page numbers (in creates: slide numbers) and the leader. It stores only these; the look is
// the Contents styles', edited in All Styles. Every change is one step in the history, for everybody, as in the
// numbering manager. Remove takes the table away; in composes its "Contents" paragraph stays, as the author's.
//
// Keys and BITV as in the other dialogs: every field has a label, Tab moves through them, Esc closes; the Shows line is
// read out when it changes.
import { computed } from 'vue'
import { useI18n } from '~/lib/i18n'
import { LEADERS, MAX_LEVEL, shows, withOption, type ContentsHost, type Leader, type Toc } from '~/lib/contents'

const { t } = useI18n()

const props = withDefaults(defineProps<{ host: ContentsHost; title: string; levels?: boolean; placesLabel?: string; placesNote?: string }>(), {
  levels: true,
  placesLabel: undefined,
  placesNote: undefined,
})
const emit = defineEmits<{ close: [] }>()

const options = computed(() => props.host.options)
const listed = computed(() => shows(props.host.entries))
const LEVELS = Array.from({ length: MAX_LEVEL }, (_, i) => i + 1)

function change<K extends keyof Toc>(key: K, value: Toc[K]) {
  if (props.host.readOnly) return
  const next = withOption(options.value, key, value)
  if (JSON.stringify(next) !== JSON.stringify(options.value)) void props.host.set(next)
}

const leaderLabel = (leader: Leader) => (leader === 'dots' ? t('· · · dots') : t('none'))

const showsLine = computed(() => {
  const { count, levels } = listed.value
  if (!count) return t('Nothing to list yet.')
  const range = levels.length === 1 ? String(levels[0]) : `${levels[0]}–${levels.at(-1)}`
  return props.levels ? t('{count} headings of levels {range}', { count, range }) : t('{count} slides', { count })
})

async function remove() {
  if (await props.host.remove()) emit('close')
}
</script>

<template>
  <Modal :title="title" :width="420" @close="emit('close')">
    <form class="form" data-testid="contents-dialog" @submit.prevent="emit('close')">
      <fieldset v-if="levels" class="row">
        <legend>{{ t('Levels') }}</legend>
        <label>{{ t('from') }}
          <select :value="options.first" :disabled="host.readOnly" data-testid="contents-first" @change="change('first', Number(($event.target as HTMLSelectElement).value))">
            <option v-for="n in LEVELS" :key="n" :value="n">{{ n }}</option>
          </select>
        </label>
        <label>{{ t('to') }}
          <select :value="options.last" :disabled="host.readOnly" data-testid="contents-last" @change="change('last', Number(($event.target as HTMLSelectElement).value))">
            <option v-for="n in LEVELS" :key="n" :value="n">{{ n }}</option>
          </select>
        </label>
      </fieldset>
      <label class="check"><input type="checkbox" :checked="options.numbers" :disabled="host.readOnly" data-testid="contents-numbers" @change="change('numbers', ($event.target as HTMLInputElement).checked)" > {{ t('Numbers') }}</label>
      <label class="check">
        <input type="checkbox" :checked="options.places" :disabled="host.readOnly" data-testid="contents-places" @change="change('places', ($event.target as HTMLInputElement).checked)" >
        {{ placesLabel ?? t('Page numbers') }}
        <span class="note">{{ placesNote ?? t('in Page view, print and PDF') }}</span>
      </label>
      <label class="row">{{ t('Leader') }}
        <select :value="options.leader" :disabled="host.readOnly || !options.places" data-testid="contents-leader" @change="change('leader', ($event.target as HTMLSelectElement).value as Leader)">
          <option v-for="l in LEADERS" :key="l" :value="l">{{ leaderLabel(l) }}</option>
        </select>
      </label>
      <section class="info">
        <h3 class="caption">{{ t('Looks') }}</h3>
        <p>{{ host.looks.join(' · ') }}</p>
        <p class="note">{{ t('Edit these styles in All Styles…') }}</p>
        <h3 class="caption">{{ t('Shows') }}</h3>
        <p aria-live="polite" data-testid="contents-shows">{{ showsLine }}</p>
      </section>
      <div class="buttons">
        <button v-if="!host.readOnly" type="button" class="btn" data-testid="contents-remove" @click="remove">{{ t('Remove {what}', { what: title }) }}</button>
        <button class="btn primary" type="submit">{{ t('Close') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.form {
  display: grid;
  gap: 12px;
}
.row {
  display: flex;
  gap: 14px;
  align-items: center;
  border: 0;
  padding: 0;
  margin: 0;
}
legend {
  float: left;
  margin-right: 10px;
}
.check {
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.note {
  color: var(--muted);
  font-size: 12px;
}
.caption {
  font-size: 12px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--ink-soft);
  margin: 6px 0 2px;
}
.info p {
  margin: 0 0 4px;
}
.buttons {
  display: flex;
  gap: 10px;
  justify-content: space-between;
}
</style>
