<script setup lang="ts">
// A single on/off control (the server settings pages' "Allow a remote model", "Require a secret…", and anywhere
// else a plain checkbox would otherwise do) — a native checkbox underneath, for keyboard and screen readers, with
// its own track-and-thumb look drawn on top (the mockups' switch; no such component existed before E3.11).
const props = defineProps<{ modelValue: boolean; label: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>

<template>
  <label class="switch" :class="{ disabled }">
    <input type="checkbox" role="switch" :checked="modelValue" :disabled="disabled" :aria-label="label" @change="emit('update:modelValue', ($event.target as HTMLInputElement).checked)" />
    <span class="track" aria-hidden="true"><span class="thumb" /></span>
  </label>
</template>

<style scoped>
.switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  flex: none;
  cursor: pointer;
}
.switch.disabled {
  cursor: default;
}
input {
  position: absolute;
  opacity: 0;
  width: 44px;
  height: 26px;
  margin: 0;
  cursor: inherit;
}
.track {
  display: block;
  width: 44px;
  height: 26px;
  border-radius: 13px;
  background: var(--faint);
  transition: background-color 0.12s ease;
}
.thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 1px 2px rgb(0 0 0 / 25%);
  transition: left 0.12s ease;
}
input:checked + .track {
  background: var(--teal);
}
input:checked + .track .thumb {
  left: 20px;
}
input:focus-visible + .track {
  outline: 2px solid var(--iris);
  outline-offset: 2px;
}
.switch.disabled .track {
  opacity: 0.5;
}
</style>
