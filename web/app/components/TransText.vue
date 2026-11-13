<script lang="ts">
// A sentence with markup inside it: `<TransText :text="t('Hand {doc} over to somebody')"><template #doc><b>{{ name }}</b></template></TransText>`.
//
// `text` is already translated (the caller's `t(...)` call is what `scripts/extract_i18n.py` finds, and it leaves a
// `{placeholder}` it was given no value for untouched). This component only cuts the translated sentence at its
// placeholders and puts each named slot there, so a translator sees and moves one whole sentence — never "Hand",
// "over to somebody who…" as separate strings — and the markup (a bold document name, say) ends up wherever the
// target language needs it. A placeholder with no slot is written out as it is.
import { defineComponent, h } from 'vue'
import { transParts } from '~/lib/trans-parts'

export default defineComponent({
  name: 'TransText',
  props: { text: { type: String, required: true }, tag: { type: String, default: 'span' } },
  setup(props, { slots, attrs }) {
    return () =>
      h(
        props.tag,
        attrs,
        transParts(props.text).map((part) => {
          if ('text' in part) return part.text
          // A placeholder with no slot is written out as it is.
          return slots[part.slot] ? slots[part.slot]!() : `{${part.slot}}`
        }),
      )
  },
})
</script>
