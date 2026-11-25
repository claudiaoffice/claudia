<script setup lang="ts">
// A colleague's selection of an object (D1223): her colour round it and her name above it, the same in all three apps.
// It lies over the object and takes no press; where it goes is the caller's (the object's own box, given as a style). The
// name sits above the box; where that would be cut off (a table scrolls inside its own frame), the caller moves it in
// with `--tag-top`, `--tag-left` and `--tag-right`.
import type { Other } from '~/lib/objects'
import { useI18n } from '~/lib/i18n'
import { inkOn } from '~/lib/people'

defineProps<{ other: Other; color: string }>()
const { t } = useI18n()
</script>

<template>
  <div
    class="other"
    data-testid="other-on-object"
    :data-other-of="other.id"
    :data-user="other.user"
    :style="{ borderColor: color }"
    :title="other.locked ? t('{user} is working on this', { user: other.user }) : t('{user} selected this', { user: other.user })"
  >
    <span class="tag" :style="{ background: color, color: inkOn(color) }">{{ other.user }}</span>
  </div>
</template>

<style scoped>
.other {
  position: absolute;
  border: 2px solid;
  pointer-events: none;
}
.tag {
  position: absolute;
  top: var(--tag-top, -20px);
  left: var(--tag-left, -2px);
  right: var(--tag-right, auto);
  font-size: 11px;
  font-weight: 500;
  padding: 1px 7px;
  border-radius: 999px;
  white-space: nowrap;
}
</style>
