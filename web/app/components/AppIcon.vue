<!-- claudia computes: "=" with a wavy lower bar on teal (design system, section 4) -->
<template>
  <svg viewBox="0 0 64 64" :width="size" :height="size" role="img" aria-label="computes">
    <rect x="2" y="2" width="60" height="60" rx="15" fill="#13917F" />
    <path d="M16 24 H48" stroke="#fff" stroke-width="5" stroke-linecap="round" />
    <path d="M16 41 C24 33 30 49 38 41 C42 37 45 38 48 40" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 24 })
</script>
