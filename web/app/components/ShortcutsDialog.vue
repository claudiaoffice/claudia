<script setup lang="ts">
// Preferences ▸ Shortcuts (D1604, D1642; mock-up `notes/mockups/menus-fit-4-shortcuts-dialog.svg`): every action of
// the app, also those that do not fit now, by menu and then by the context menu that alone has it, each with its key
// and when it fits. The switch shows What Fits Now or Everything; under Everything what does not fit is muted and
// tagged "not for you", "not now" or "not here". Then the window's keys that are no menu entry (F6, Ctrl+H) and what
// is not a key at all (a drag, a double-click), which have no place in the menus.
//
// Read-only (D122): nothing here remaps a key.
import { computed, ref } from 'vue'
import { useI18n } from '~/lib/i18n'
import type { ShortcutGroup } from '~/lib/menus/assemble'

const { t } = useI18n()

const props = defineProps<{
  /** The definition's actions, judged now (`AssembledMenus.listing`). */
  groups: ShortcutGroup[]
  /** The window's own keys that are no menu entry, already written as a person reads them. */
  others: { label: string; keys: string }[]
  /** What is no key combination: a mouse gesture, a typed convention, as [what to do, what it does]. */
  extra?: [string, string][]
}>()
const emit = defineEmits<{ close: [] }>()

const everything = ref(false)
const query = ref('')

/** The groups as the switch and the search field leave them; a group with nothing left goes. */
const shown = computed(() => {
  const words = query.value.trim().toLowerCase()
  const found = (...texts: (string | null)[]) => !words || texts.some((text) => text?.toLowerCase().includes(words))
  return props.groups
    .map((group) => ({ ...group, rows: group.rows.filter((row) => (everything.value || row.fits) && found(row.label, row.keys, row.when)) }))
    .filter((group) => group.rows.length)
})
const others = computed(() => {
  const words = query.value.trim().toLowerCase()
  const found = (...texts: string[]) => !words || texts.some((text) => text.toLowerCase().includes(words))
  return [...props.others.map((o) => [o.keys, o.label] as [string, string]), ...(props.extra ?? [])].filter(([keys, label]) => found(keys, label))
})
</script>

<template>
  <Modal :title="t('Shortcuts')" :width="860" @close="emit('close')">
    <div class="head">
      <div class="switch" role="radiogroup" :aria-label="t('Which actions')" data-testid="shortcuts-switch">
        <button type="button" role="radio" :aria-checked="!everything" :class="{ on: !everything }" @click="everything = false">{{ t('What Fits Now') }}</button>
        <button type="button" role="radio" :aria-checked="everything" :class="{ on: everything }" @click="everything = true">{{ t('Everything') }}</button>
      </div>
      <input v-model="query" class="find" type="search" :placeholder="t('Find an action…')" :aria-label="t('Find an action')" >
    </div>
    <div class="list" data-testid="shortcuts-list">
      <section v-for="group in shown" :key="group.title">
        <h3>{{ group.title }}</h3>
        <table>
          <tbody>
            <tr v-for="row in group.rows" :key="row.id" :class="{ off: !row.fits }" :data-action="row.id">
              <td class="keys mono">{{ row.keys ?? '' }}</td>
              <td class="label">{{ row.label }}</td>
              <td class="when">{{ row.when }}</td>
              <td class="tag"><span v-if="row.tag" class="chip">{{ row.tag }}</span></td>
            </tr>
          </tbody>
        </table>
      </section>
      <section v-if="others.length">
        <h3>{{ t('Other keys') }}</h3>
        <table>
          <tbody>
            <tr v-for="[keys, label] in others" :key="keys + label">
              <td class="keys mono">{{ keys }}</td>
              <td class="label" colspan="3">{{ label }}</td>
            </tr>
          </tbody>
        </table>
      </section>
      <p v-if="!shown.length && !others.length" class="none">{{ t('No action has these words.') }}</p>
    </div>
    <button class="btn primary" type="button" @click="emit('close')">{{ t('Close') }}</button>
  </Modal>
</template>

<style scoped>
.head {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.switch {
  display: flex;
  align-self: flex-end;
  gap: 2px;
  padding: 2px;
  border-radius: 999px;
  border: 1px solid var(--line-field);
}
.switch button {
  font: inherit;
  font-size: 13px;
  padding: 4px 14px;
  border: 0;
  border-radius: 999px;
  background: none;
  color: var(--app-text);
  cursor: pointer;
}
.switch button.on {
  background: var(--surface);
  box-shadow: 0 0 0 1px var(--iris);
  font-weight: 600;
}
.find {
  font: inherit;
  padding: 6px 10px;
  border: 1px solid var(--line-field);
  border-radius: 6px;
}
.list {
  max-height: 60vh;
  overflow: auto;
}
h3 {
  margin: 16px 0 4px;
  font-size: 13px;
  color: var(--iris);
}
table {
  width: 100%;
  border-collapse: collapse;
}
td {
  padding: 5px 8px 5px 0;
  border-top: 1px solid var(--line);
  vertical-align: baseline;
}
.keys {
  font-size: 12px;
  white-space: nowrap;
  color: var(--app-text); /* --app-dark as literal text fails contrast in dark mode — the owner's 2026-11-06 report */
}
/* what says why is drawn in the muted ink (about 5:1), not in a greyed entry's paler grey (D1642, BITV 1.4.3) */
.when,
tr.off .keys,
tr.off .label {
  color: var(--muted);
  font-size: 12px;
}
tr.off .label {
  font-size: inherit;
}
.tag {
  text-align: right;
}
.chip {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 999px;
  border: 1px solid var(--line-field);
  color: var(--muted);
  white-space: nowrap;
}
.none {
  color: var(--muted);
}
.btn {
  justify-self: start;
  margin-top: 12px;
}
</style>
