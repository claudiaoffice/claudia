<script setup lang="ts">
// The strip that says a computation is being followed (E6.23, D297; mock computes-follow-computation-sheet): which cell,
// how many of the connected ones take which part, whether every connected cell lights up (group) or only those this
// one depends on and those that depend on it (chain), and the way out. Roles are told by shape as well as colour (BITV).
import { computed } from 'vue'
import { useI18n } from '~/lib/i18n'
import { followLabel, ROLE_SHAPE, roleCounts, type Reach, type Trace } from '~/lib/follow'

const props = defineProps<{ trace: Trace }>()
const emit = defineEmits<{ reach: [reach: Reach]; stop: [] }>()
const { t } = useI18n()

const counts = computed(() => roleCounts(props.trace))
const label = computed(() => followLabel(props.trace))
</script>

<template>
  <div class="pill" role="status" :aria-label="t('Following {cell}', { cell: label })">
    <strong>{{ t('Following {cell}', { cell: label }) }}</strong>
    <template v-if="trace.connected">
      <span class="role"><span class="mark" :class="ROLE_SHAPE.input" data-role="input" aria-hidden="true" />{{ counts.input === 1 ? t('{n} input', { n: 1 }) : t('{n} inputs', { n: counts.input }) }}</span>
      <span class="role"><span class="mark" :class="ROLE_SHAPE.calc" data-role="calc" aria-hidden="true" />{{ counts.calc === 1 ? t('{n} calculation', { n: 1 }) : t('{n} calculations', { n: counts.calc }) }}</span>
      <span class="role"><span class="mark" :class="ROLE_SHAPE.output" data-role="output" aria-hidden="true" />{{ counts.output === 1 ? t('{n} result', { n: 1 }) : t('{n} results', { n: counts.output }) }}</span>
      <span v-if="trace.truncated" class="muted">{{ t('and more further out') }}</span>
    </template>
    <span v-else class="muted">{{ t('This cell is not part of a computation.') }}</span>
    <span class="seg" role="group" :aria-label="t('How far the lights reach')">
      <button type="button" :aria-pressed="trace.reach === 'group'" @click="emit('reach', 'group')">{{ t('Group') }}</button>
      <button type="button" :aria-pressed="trace.reach === 'chain'" @click="emit('reach', 'chain')">{{ t('Chain') }}</button>
    </span>
    <button type="button" class="stop" :title="t('Stop following (Esc)')" :aria-label="t('Stop following')" @click="emit('stop')">×</button>
  </div>
</template>

<style scoped>
.pill {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 5px 8px 5px 12px;
  border: 1px solid var(--line-field);
  border-radius: 999px;
  background: var(--surface);
  box-shadow: var(--shadow);
  font-size: 12.5px;
  white-space: nowrap;
}
.role {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.muted {
  color: var(--muted);
}
.mark {
  display: inline-block;
  width: 9px;
  height: 9px;
}
.mark[data-role='input'] {
  background: var(--apricot);
  border-radius: 50%;
}
.mark[data-role='calc'] {
  background: var(--iris);
  transform: rotate(45deg) scale(0.85);
}
.mark[data-role='output'] {
  background: var(--teal);
}
.seg {
  display: inline-flex;
  border: 1px solid var(--line-field);
  border-radius: 999px;
  overflow: hidden;
}
.seg button {
  border: 0;
  background: none;
  padding: 2px 10px;
  font-size: 12px;
  color: var(--text);
  cursor: pointer;
}
.seg button[aria-pressed='true'] {
  background: var(--app-dark);
  color: #fff;
}
.stop {
  border: 0;
  background: none;
  font-size: 16px;
  line-height: 1;
  padding: 2px 6px;
  color: var(--muted);
  cursor: pointer;
}
</style>
