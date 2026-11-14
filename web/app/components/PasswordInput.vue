<script setup lang="ts">
// Every password field in Claudia (sheet 12, D448): an input with an eye at its right end that shows and hides what
// was typed. A drop-in for `<input type="password">`: v-model, and every other attribute (name, autocomplete,
// placeholder, required, readonly, autofocus) goes to the input itself. The eye is a toggle button of its own (Tab,
// then Space), never submits the form, and the field starts hidden again whenever it is shown anew (its dialog closed
// and opened). The browser's own reveal button (Edge) is switched off, so there is never a second eye.
import { ref } from 'vue'
import { useI18n } from '~/lib/i18n'

defineOptions({ inheritAttrs: false })
const model = defineModel<string>({ default: '' })
const { t } = useI18n()
const visible = ref(false)
</script>

<template>
  <span class="password">
    <input v-bind="$attrs" v-model="model" :type="visible ? 'text' : 'password'" spellcheck="false" autocapitalize="off" >
    <button
      type="button"
      class="eye"
      :aria-pressed="visible"
      :aria-label="t('Show password')"
      :title="visible ? t('Hide password') : t('Show password')"
      @click="visible = !visible"
    >
      <svg width="20" height="14" viewBox="0 0 20 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true">
        <path d="M1 7c3.6-6.6 14.4-6.6 18 0-3.6 6.6-14.4 6.6-18 0z" />
        <circle cx="10" cy="7" r="2.6" />
        <path v-if="visible" d="M3 13 17 1" />
      </svg>
    </button>
  </span>
</template>

<style scoped>
.password {
  position: relative;
  display: block;
  min-width: 0;
  flex: 1 1 auto;
}
/* doubled class: wins over a parent's own `:deep(input)` padding, so text never runs under the eye */
.password.password input {
  width: 100%;
  min-width: 0;
  padding-right: 40px;
}
.password input::-ms-reveal,
.password input::-ms-clear {
  display: none;
}
.eye {
  position: absolute;
  top: 50%;
  right: 4px;
  transform: translateY(-50%);
  display: grid;
  place-items: center;
  width: 32px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}
.eye:hover {
  color: var(--text);
  background: var(--app-soft);
}
</style>
