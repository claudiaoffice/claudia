<script setup lang="ts">
// The fonts this document asks for and this server does not have (E1.9, D1306): said when the document opens, never in
// the way of it. An administrator is offered "Get", which goes to Server settings ▸ Fonts; everybody else is told to
// ask one. The server refuses anything but an administrator's own request there, whatever this page shows.
import { computed, onMounted, ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { bannerSentence, mayOfferGet, type FontReport } from '~/lib/font-report'
import { useI18n } from '~/lib/i18n'
import { readToken } from '~/lib/admin-session'
import { adminUrl } from '~/lib/server-bookmarks'

const { t } = useI18n()
const props = defineProps<{ session: BaseSession }>()

const report = ref<FontReport>({ checked: false, missing: [] })
const dismissed = ref(false)
const sentence = computed(() => (dismissed.value ? null : bannerSentence(report.value)))
const administrator = ref(false)

onMounted(async () => {
  administrator.value = readToken() !== null // this tab is signed in to the server's settings; the server checks again
  report.value = await props.session.fontReport()
})
const getUrl = computed(() => `${adminUrl(location.origin)}#fonts`)
</script>

<template>
  <div role="status">
    <div v-if="sentence" class="banner fonts" data-testid="font-banner">
      <span>{{ sentence }}</span>
      <a v-if="mayOfferGet(administrator)" class="btn get" :href="getUrl" target="_blank" rel="noopener">{{ t('Get') }}</a>
      <span v-else>{{ t('Ask an administrator to add it.') }}</span>
      <button type="button" class="btn" @click="dismissed = true">{{ t('Dismiss') }}</button>
    </div>
  </div>
</template>

<style scoped>
.banner.fonts {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 6px 12px;
  background: var(--panel-2, #2a2342);
  color: var(--ink, inherit);
  font-size: 13px;
}
.banner.fonts span {
  flex: 1;
}
</style>
