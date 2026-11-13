<script setup lang="ts">
// The document's colours, by what they mean (D200–D202).
//
// A style groups things that serve the same purpose; a palette groups colours that carry the same meaning. Change
// one here and everything that meant it follows — every style, in every app, at once. That reach is the point, and
// the reason a change is worth showing before it happens.
//
// Nothing is prevented. A person may pick any colour; what the dialog owes them is the truth about what it will
// cost, in words they can act on and never as a ratio (D202).
import { computed, ref, watch } from 'vue'
import { contrast, troubleWith, troubles, type ColourRole } from '~/lib/roles'
import { roleIn } from '~/lib/roles'
import type { StyleHost } from '~/lib/style-host'

const props = defineProps<{ host: StyleHost; builtin?: ColourRole[] }>()
const emit = defineEmits<{ close: []; reset: [] }>()

const picked = ref(props.host.roles[0]?.id ?? '')
watch(
  () => props.host.roles.map((r) => r.id).join(),
  (ids) => {
    if (!ids.split(',').includes(picked.value)) picked.value = props.host.roles[0]?.id ?? ''
  },
)

const current = computed(() => props.host.roles.find((r) => r.id === picked.value))
const off = computed(() => props.host.readOnly)

/** How many styles name each role, at any opacity: the count that says how far a change will reach. */
const uses = computed(() => {
  const counted: Record<string, number> = {}
  for (const style of props.host.styles)
    for (const value of Object.values(style.css)) {
      for (const match of value.matchAll(/@([a-z0-9][a-z0-9-]{0,39})/g)) {
        const id = match[1]!
        counted[id] = (counted[id] ?? 0) + 1
      }
    }
  return counted
})

/** What the selected role is read against, and whether it holds up — said in words, never as a figure. */
const readings = computed(() =>
  props.host.readings
    .filter((r) => r.foreground === picked.value || r.background === picked.value)
    .map((r) => ({ ...r, said: troubleWith(r, props.host.roles) })),
)

/** Every failing reading in the document, worst first: the standing state of the palette. */
const failing = computed(() => troubles(props.host.readings).map((r) => troubleWith(r, props.host.roles)))

/** The styles a change to the selected role would reach, which is what "see it before it happens" means. */
const reached = computed(() =>
  props.host.styles.filter((s) =>
    Object.values(s.css).some((v) => roleIn(v)?.role === picked.value || v.includes(`@${picked.value}`)),
  ),
)

const typed = ref('')
watch(current, (role) => (typed.value = role?.colour ?? ''), { immediate: true })
const valid = computed(() => /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(typed.value.trim()))
const changed = computed(() => valid.value && typed.value.trim().toUpperCase() !== current.value?.colour.toUpperCase())

/** What this change would cost, before it is made: the same pairings, worked out against the colour being typed. */
const wouldBreak = computed(() => {
  if (!changed.value || !current.value) return []
  const after = new Map(props.host.roles.map((r) => [r.id, r.colour]))
  after.set(current.value.id, typed.value.trim())
  return props.host.readings
    .filter((r) => r.foreground === picked.value || r.background === picked.value)
    .filter((r) => contrast(after.get(r.foreground) ?? '#000', after.get(r.background) ?? '#fff') < r.floor)
    .map((r) => troubleWith({ ...r, ok: false }, props.host.roles))
})

async function commit() {
  if (changed.value && current.value) await props.host.setRole(current.value.id, typed.value.trim())
}
</script>

<template>
  <Modal title="Colours" :width="540" @close="emit('close')">
    <p class="lead">A colour here means something. Change it and everything that means the same thing changes with it.</p>

    <ul class="roles" role="listbox" aria-label="Colour roles" data-testid="role-list">
      <li v-for="r in host.roles" :key="r.id" role="option" :aria-selected="r.id === picked" :data-role="r.id">
        <button type="button" :class="{ on: r.id === picked }" @click="picked = r.id">
          <i :style="{ background: r.colour }" />
          <span class="name">{{ r.name }}</span>
          <span class="why">{{ r.purpose }}</span>
          <span class="count mono">{{ uses[r.id] ?? 0 }}</span>
        </button>
      </li>
    </ul>

    <section v-if="current" class="chosen" :aria-label="current.name">
      <header>
        <i :style="{ background: current.colour }" />
        <span class="name">{{ current.name }}</span>
        <span class="used">used by {{ uses[current.id] ?? 0 }} {{ (uses[current.id] ?? 0) === 1 ? 'style' : 'styles' }}</span>
        <label class="hex">
          <span>Hex</span>
          <input v-model="typed" class="mono" spellcheck="false" :disabled="off" :aria-label="`${current.name} as hex`" @keydown.enter.prevent="commit" >
        </label>
        <button class="btn primary" type="button" :disabled="off || !changed" data-testid="apply-role" @click="commit">Change it</button>
      </header>

      <!-- warned, never prevented: what it will cost, in plain words -->
      <div v-if="wouldBreak.length" class="warn" data-testid="would-break">
        <p v-for="said in wouldBreak" :key="said ?? ''">{{ said }}</p>
        <p class="anyway">You can change it anyway — this is a warning, not a refusal.</p>
      </div>

      <div v-if="readings.length" class="readings">
        <!-- These verdicts are about the colour the role *has*. While a different one is typed above, the warning
             there is about what it *would* become, and saying so keeps the two from reading as contradictions. -->
        <h4>Read against{{ changed ? ' — as it is now' : '' }}</h4>
        <ul>
          <li v-for="r in readings" :key="`${r.foreground}-${r.background}`">
            <span class="pair">{{ host.roles.find((x) => x.id === r.foreground)?.name ?? r.foreground }} on {{ host.roles.find((x) => x.id === r.background)?.name ?? r.background }}</span>
            <span class="verdict" :class="{ bad: !r.ok }">{{ r.ok ? (r.words ? 'Easy to read' : 'Easy to see') : r.words ? 'Hard to read' : 'Too faint' }}</span>
          </li>
        </ul>
      </div>

      <div v-if="reached.length" class="reached">
        <h4>What changes with it</h4>
        <ul>
          <li v-for="s in reached" :key="s.id">{{ s.name }}</li>
        </ul>
      </div>
    </section>

    <p v-if="failing.length" class="standing" data-testid="standing-trouble">
      <strong>In this document now:</strong>
      <span v-for="said in failing" :key="said ?? ''">{{ said }}</span>
    </p>

    <div class="buttons">
      <button v-if="builtin?.length" class="btn" type="button" :disabled="off" data-testid="reset-palette" @click="emit('reset')">The colours it started with</button>
      <button class="btn primary" type="button" @click="emit('close')">Done</button>
    </div>
  </Modal>
</template>

<style scoped>
.lead {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--muted);
  line-height: 1.5;
}
.roles {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 1px;
  max-height: 232px;
  overflow-y: auto;
}
.roles button {
  display: grid;
  grid-template-columns: 22px 1fr auto;
  grid-template-areas: 'swatch name count' 'swatch why count';
  align-items: center;
  gap: 0 11px;
  width: 100%;
  padding: 7px 9px;
  border: 0;
  border-radius: 8px;
  background: none;
  text-align: left;
  cursor: pointer;
}
.roles button:hover {
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode */
}
.roles button.on {
  background: color-mix(in srgb, var(--app) 13%, transparent);
}
.roles i,
.chosen i {
  grid-area: swatch;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  box-shadow: inset 0 0 0 1px rgb(31 26 51 / 22%);
}
.roles .name {
  grid-area: name;
  font-size: 13.5px;
}
.roles .why {
  grid-area: why;
  font-size: 11.5px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.roles .count {
  grid-area: count;
  font-size: 11px;
  color: var(--muted);
}
.chosen {
  margin-top: 12px;
  padding: 11px;
  border-radius: 10px;
  background: var(--page);
  display: grid;
  gap: 10px;
}
.chosen header {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
}
.chosen .name {
  font-size: 13.5px;
  font-weight: 500;
}
.used {
  flex: 1;
  font-size: 11.5px;
  color: var(--muted);
}
.hex {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--muted);
}
.hex input {
  width: 92px;
  height: 28px;
  padding: 0 7px;
  border: 1px solid var(--line-field); /* a control boundary, not a divider */
  border-radius: 7px;
  font-size: 12px;
}
.warn {
  padding: 9px 11px;
  border-radius: 8px;
  /* Literal `white`, so the warning stays light in either theme. */
  background: color-mix(in srgb, var(--apricot) 15%, white);
  color: var(--ink);
  font-size: 12px;
  line-height: 1.5;
}
.warn p {
  margin: 0;
}
.warn .anyway {
  margin-top: 5px;
  color: color-mix(in srgb, var(--ink) 70%, white);
}
h4 {
  margin: 0 0 5px;
  font: 600 10.5px/1 var(--font-ui);
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--muted);
}
.readings ul,
.reached ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 3px;
  font-size: 12px;
}
.readings li {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.pair {
  flex: 1;
}
.verdict {
  padding: 1px 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--teal) 16%, white);
  color: #0f6b5e;
  font-size: 10.5px;
}
.verdict.bad {
  background: color-mix(in srgb, var(--apricot) 26%, white);
  color: #7a4710;
}
.reached li {
  color: var(--muted);
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
.standing {
  margin: 12px 0 0;
  display: grid;
  gap: 2px;
  font-size: 11.5px;
  color: var(--muted);
  line-height: 1.5;
}
</style>
