<script setup lang="ts">
// The health indicator in the top bar (E3.11, "knowing which server you're on" — canvas note s5): always visible,
// not only while reconnecting, because which server a document actually lives on is worth knowing at a glance.
// Hovering or clicking it opens the same detail every time: the server's label and address, whether the
// connection is encrypted, a fresh latency reading, and the way into that server's own settings pages.
import { computed, ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { canManageNow, friendlyLabel, indicatorLabel, manageUrl, resolveOrigin, statusWord } from '~/lib/connection'

const props = defineProps<{ session: BaseSession }>()

const state = props.session.state
const button = ref<HTMLElement | null>(null)
const at = ref<{ x: number; y: number } | null>(null)
const ping = ref<number | null>(null)
const pinging = ref(false)

// `location` is a browser global (the app has no SSR); `state.host` can differ from the page's own host — the Open
// dialog's `?server=`/bookmark switching connects a page to a server other than the one it was loaded from.
const origin = computed(() => resolveOrigin(state.host, location.protocol, location.host))
const host = computed(() => state.host || location.host)
const label = computed(() => friendlyLabel(origin.value, host.value))
const secure = computed(() => location.protocol === 'https:')
const aria = computed(() => indicatorLabel(label.value, state.status))
const statusLine = computed(() => {
  const word = statusWord(state.status)
  if (state.status !== 'open') return word
  if (pinging.value) return `${word} · …`
  return ping.value === null ? word : `${word} · ${ping.value} ms`
})

async function toggle() {
  if (at.value) {
    at.value = null
    return
  }
  const r = button.value?.getBoundingClientRect()
  const width = 260
  at.value = { x: (r?.right ?? 0) - width, y: (r?.bottom ?? 0) + 8 }
  if (state.status !== 'open') return
  pinging.value = true
  ping.value = await props.session.ping()
  pinging.value = false
}

function close() {
  at.value = null
}
</script>

<template>
  <div class="indicator">
    <button ref="button" type="button" class="health" :class="state.status" :aria-label="aria" aria-haspopup="dialog" :aria-expanded="!!at" @click="toggle">
      <svg width="15" height="15" viewBox="0 0 20 20" aria-hidden="true">
        <rect x="2" y="12" width="3" height="6" rx="1" />
        <rect x="8.5" y="8" width="3" height="10" rx="1" />
        <rect x="15" y="3" width="3" height="15" rx="1" />
      </svg>
    </button>
    <Popover v-if="at" bare :x="at.x" :y="at.y" :width="260" :anchor="button" label="Connection details" @close="close">
      <div class="tooltip">
        <p class="line">
          <span class="dot" :class="state.status" aria-hidden="true" />
          <span>{{ statusLine }}</span>
        </p>
        <p class="label">{{ label }}</p>
        <p class="host">{{ host }}</p>
        <p class="tls" :class="{ insecure: !secure }">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 018 0v3" />
          </svg>
          <span>{{ secure ? 'TLS verified' : 'Not encrypted' }}</span>
        </p>
        <hr >
        <!-- A link to this server's own settings only makes sense while its connection is actually open (D171
             covered a different gate — viewer permission — and deliberately left this one always visible; whether
             the link currently leads anywhere is a question this component already answers for itself, unlike
             permission, which it can't check without a cross-origin fetch). Reconnecting/closed renders a plain,
             inert span instead of a dead-looking live link. -->
        <a v-if="canManageNow(state.status)" class="manage" :href="manageUrl(origin)">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="3" />
            <path
              d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"
            />
          </svg>
          Manage this server…
        </a>
        <span v-else class="manage disabled" aria-disabled="true">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="3" />
            <path
              d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"
            />
          </svg>
          Manage this server…
        </span>
      </div>
    </Popover>
  </div>
</template>

<style scoped>
.indicator {
  display: flex;
}
.health {
  position: relative;
  width: 30px;
  height: 30px;
  flex: none;
  border-radius: 50%;
  border: none;
  background: var(--faint);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
}
.health rect {
  fill: currentColor;
}
.health.open {
  background: color-mix(in srgb, var(--teal) 12%, transparent);
  color: var(--teal);
}
.health.connecting,
.health.reconnecting {
  background: color-mix(in srgb, var(--apricot) 14%, transparent);
  color: var(--apricot);
}

/* The tooltip's own chrome is fixed-dark in both themes, like a native tooltip: `--ink`/`--paper` are the two
 * tokens the design system never flips for dark mode (tokens.css), so this reads the same regardless of page
 * theme — exactly what the mockup draws. */
.tooltip {
  width: 260px;
  background: var(--ink);
  color: var(--paper);
  border-radius: 11px;
  padding: 14px 16px;
  box-shadow: 0 14px 34px rgb(31 26 51 / 35%);
}
.line {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 0 10px;
  font-weight: 500;
  font-size: 13px;
}
.dot {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: color-mix(in srgb, var(--paper) 55%, transparent);
}
.dot.open {
  background: var(--teal-light);
}
.dot.connecting,
.dot.reconnecting {
  background: var(--apricot-light);
}
.label {
  margin: 0 0 2px;
  font-weight: 600;
  font-size: 13.5px;
}
.host {
  margin: 0 0 10px;
  font: 12px var(--font-mono);
  color: color-mix(in srgb, var(--paper) 60%, transparent);
  word-break: break-all;
}
.tls {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 11px;
  font-size: 12px;
  color: color-mix(in srgb, var(--paper) 70%, transparent);
}
.tls.insecure {
  color: var(--apricot-light);
}
hr {
  border: none;
  height: 1px;
  background: color-mix(in srgb, var(--paper) 15%, transparent);
  margin: 0 0 9px;
}
.manage {
  display: flex;
  align-items: center;
  gap: 7px;
  color: color-mix(in srgb, var(--paper) 85%, transparent);
  font: 500 12px var(--font-ui);
  text-decoration: none;
}
.manage:hover {
  color: var(--paper);
}
.manage.disabled {
  opacity: 0.45;
  cursor: default;
  pointer-events: none;
}
</style>
