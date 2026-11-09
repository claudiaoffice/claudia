// The text as a StyleHost: its paragraphs are what the style menu styles.
import type { StyleHost } from './style-host'
import type { TextSession } from './text-session'

export function textStyleHost(session: TextSession): StyleHost {
  return {
    get styles() {
      return session.state.styles
    },
    get current() {
      return session.styleView(session.currentStyle()) ?? session.state.styles[0]
    },
    get readOnly() {
      return session.readOnly
    },
    noun: 'paragraph',
    // A paragraph has words and no box of its own: no fill, no border. A shape has both (D178, D181).
    parts: { words: true, box: false },
    get roles() {
      return session.state.palette?.roles ?? []
    },
    get readings() {
      return session.state.palette?.readings ?? []
    },
    uses: () => session.uses(),
    apply: async (style) => (await session.setStyle(style)) ?? false,
    change: (style, edit) => session.changeStyle(style, edit),
    deviate: (edit) => session.deviateStyle(edit),
    rename: (style, name) => session.renameStyle(style, name),
    check: (text) => session.checkCss(text),
    setRole: (role, colour) => session.setRole(role, colour),
  }
}
