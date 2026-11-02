<!-- The icon of an app (design system, section 4): computes is "=" with a wavy lower bar on teal, composes a pen nib on rose. -->
<template>
  <svg v-if="app === 'composes'" viewBox="0 0 64 64" :width="size" :height="size" role="img" aria-label="composes">
    <rect x="2" y="2" width="60" height="60" rx="15" fill="#D6477A" />
    <path d="M32 11 L42 32 L32 46 L22 32 Z" fill="#fff" />
    <circle cx="32" cy="29" r="2.6" fill="#D6477A" />
    <path d="M32 31.5 L32 46" stroke="#D6477A" stroke-width="1.8" stroke-linecap="round" />
    <path d="M16 52 H48" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".55" />
  </svg>
  <svg v-else viewBox="0 0 64 64" :width="size" :height="size" role="img" aria-label="computes">
    <rect x="2" y="2" width="60" height="60" rx="15" fill="#13917F" />
    <path d="M16 24 H48" stroke="#fff" stroke-width="5" stroke-linecap="round" />
    <path d="M16 41 C24 33 30 49 38 41 C42 37 45 38 48 40" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number; app?: string }>(), { size: 24, app: 'computes' })
</script>
