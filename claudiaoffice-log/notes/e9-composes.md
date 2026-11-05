# claudia composes — model, web demo and styling

Three notes merged: the standalone web demo (2026-11-02), fitting it into the repo (2026-11-02) and the styling work
(2026-11-03). Moved here 2026-11-05.

## 1. The standalone demo (history)

The first iteration was a separate Nuxt app with documents in `localStorage`. It showed: the computes layout; a
styles-first model; a ± n words lock around another person's cursor; flow and page view; AI edits as suggestions
(accepting makes the accepter's command); an authorship view; chat commands `@ai outline|count|help`; commands
coalesced within 2 s. Checks then: 104 unit tests, `vue-tsc`, 19 browser checks.

It was reworked into the repository as a composes view in `web/` plus a real text app on the server. What happened to
each part:

| Standalone | In the repo |
|---|---|
| Layout, menus, docked panel, footer | The shared `TopBar`, `MenuBar`, `SidePanel`, `OpenDialog`, `HelpDialog`, `ShareDialog`; rose theme via `data-app="composes"` |
| One node per paragraph plus a style id | `TextModel` in `claudia-composes`: stable paragraph ids, named styles, runs per paragraph |
| Authorship as an `author` mark | Runs `[length, author, via]` kept as model state and rebuilt by replay (see the open point below) |
| ± n words lock, client side | Server: `look` and `hold`, enforced by the kernel for everybody (D47); the client shows carets, zones and refusals |
| Suggestions by a client-side script | Server: `suggest` (assistant only), `accept_suggestion`, `reject_suggestion`; the assistant `TextEngine` is a scripted stand-in (D56) |
| Documents in `localStorage` | Documents on the server (`--app composes`); the open dialog lists them |
| Bold, italic, underline, bullets | **Dropped for now** by agreement; they need inline marks and lists in the model |
| Chat commands `outline`, `count`, `help` | **Not ported.** The stand-in understands `review`/`check` and `help` |
| Coalescing within 2 s | One history step per word; the kernel has no undo grouping |

## 2. The text model and the server methods

**`packages/claudia-composes`** — the real text model, where there had been a stub:

- `model.py` `TextModel`: paragraphs with stable ids never reused, named styles (D62), authorship runs, suggestions as
  proposals (D63). State schema 2, then 3 with styles in the document; older states still load.
- `commands.py`, `spans.py`, `region.py`, `runs.py`, `events.py`: commands (split, join, insert, delete, style,
  suggest, accept and so on), "where does a span go after this command" (`TextCommand.follow`), text regions for
  cursors and zones, run arithmetic, state events.

**`packages/claudia-server`** — `composes.py` with `blocks`, `suggestions`, `replace_text`, `set_style`, `look`,
`hold`, `suggest`, `accept_suggestion`, `reject_suggestion`, and later the five styling methods. One request is one
history step. The AI account has no direct write path (D63): it suggests, people accept, and an accepted suggestion
is an ordinary edit by the accepter with `via=ai`. `standin_text.py` is the scripted `TextEngine` (spelling,
wordiness, intensifiers, double spaces, long sentences).

**`web/`** — `lib/base-session.ts` (shared), `text-session.ts` (replica of the text, per-word buffered typing, zone
placement, undo and redo), `blocks.ts`, `markdown.ts`, `open.ts`, `sample.ts`; `TextWorkspace.vue`, `TextEditor.vue`
(its own `contenteditable`, where the browser never edits the page and only server events do), `StyleBar.vue`,
`SuggestionList.vue`. Flow and page view, "who wrote what" shading, colleagues' carets and ± 3-word zones, Save as
Markdown.

## 3. Styling (E1.10, E5.13, E9.7, E9.8)

The request: composes takes the lead on styling text; CSS is the styling language (D73, D75); one context menu with a
colour picker, font picker, size and font properties, a design all three apps can use, and a switch between the
controls and the native CSS of a style. Scope chosen with the owner: **paragraph styles first**, and **the shared
style model lives in `claudia-core`**.

**Kernel (`claudia-core` 0.5.0)** — `css.py`: the versioned CSS allow-list (`CSS_VERSION` 1) with `validate_css`,
`parse_css` (line-numbered problems) and `format_css` (a fixed property order). Allowed: font-family (names only, at
most 20), font-size, weight, style, text-decoration, colour, background-colour, text-align, line-height, letter and
word spacing, margins, padding, per-side borders, and `fill`, `stroke`, `stroke-width` for shapes. Refused: `url()`,
`var()`, `calc()`, `!important`, `@`-rules, comments, and `; { } < > \`. `styles.py`: `StyleDef`, `StyleBook`
(inheritance via `based_on`, storing only differences, unique names and ids, provisional names), the event
`StylesChanged`, and the commands `CreateStyle`, `ChangeStyle`, `RenameStyle`, `RemoveStyle` (only as the undo of a
create). A change by a colleague, a rename, or a child style makes a later undo refuse with `UndoConflict`, never
overwrite.

**composes** — styles live in the document. The built-ins are Body text plus Title, Heading 1/2, Quote, Remark and
Definition, all based on Body text, so changing Body text changes all that do not override the property.
`next_style` decides what Enter starts after a heading.

**Web** — `lib/style-css.ts` (pure helpers, tested), `lib/style-host.ts` (`StyleHost` interface and `StyleEditor`
rules), `lib/text-style-host.ts`, `lib/fonts.ts`, `lib/palette.ts`; components `Popover`, `StyleMenu`, `StyleSpec`,
`StyleColorPicker`, `StyleFontPicker`, `StyleSizeField`, `StyleCssEditor`, `StylesDialog`. The page draws each
paragraph from its computed CSS; the element only says heading or quote. Open the menu with right-click, Shift+F10, or
Format ▸ "Look of this style…"; Format ▸ "All styles…" lists styles with use counts and renames.

### How the menu behaves (decisions taken while building — to confirm)

1. **Styles first.** The top of the menu is the style gallery, with a preview in the style's own type, a use count and
   a *to name* flag.
2. **Deviate by default.** In the *Look* section a change goes to **This paragraph only** (creating a new style such
   as "Body text (changed)", flagged *to name*) or to **Every use of "X" (N)**. A style that still waits for its name
   is the person's own, so changes go into it and the default flips to *every use*; the choice resets when the caret
   moves to another style. Edits are queued, so a deviation completes before the next edit decides where to go.
3. **A Controls | CSS switch**, remembered. The CSS view shows the style's own declarations; the server checks it
   while typing and errors are listed with their line; Apply (Ctrl+Enter) is off until it is valid. A collapsed list
   shows which parent each inherited property comes from.
4. **The name invitation** appears once per style, quietly, inside the menu; "Not now" dismisses it; it never blocks
   typing.
5. **Allow-list v1 is wider than the first proposal in E1.10:** padding and per-side borders are in, needed for Quote,
   Remark and Definition. The "Remark" label that used to be drawn by CSS `::before` is dropped, being chrome rather
   than style.
6. Style changes do not respect locks yet, because a style is not in a text range; `deviate_style` refuses more than
   2000 paragraphs.
7. Built-in styles are defined in code and seeded into every new document; on replay of old logs they are re-seeded.

## 4. Open points and gaps

- **Inline marks** (bold, italic, underline), lists and tables. Dropped by agreement and still the biggest hole in the
  model.
- **Character styles** are the next step after paragraph styles.
- **The authorship question (E9.10).** The story says authorship is "derived by replaying the log"; in the repo the
  runs are model state that replay rebuilds. Same result, different property — it is stored after all. To confirm or
  change, because it constrains how text commands keep the identity of moved and pasted runs (E9.1).
- **The AI can still write through the generic `apply` method.** `replace_text` and `set_style` refuse it, but the
  generic path is not closed (SEC-10).
- Redacting a propose step before its accept may break replay.
- Undoing a reject or dismiss reopens the suggestion — intended? Needs a decision.
- Typing is one history step per word; the kernel has no undo grouping.
- IME input is minimal: composed text is sent at composition end.
- The whole text is loaded through `blocks`, with no windowing for very long documents.
- The page view is approximate — a sheet with margins, no real breaks, no headers or footers (E9.4, E9.14).
- Text typed in the browser is lost if the request fails.
- The stand-in assistant does not propose around other people's locks; lock conflicts surface as an error toast with
  no automatic retry.
- The menus are defined in the composes workspace component; the manifest of E5.1 is still to be done, and the Linux
  shell maps six web menus onto four native ones (UX-09).

## 5. Next steps as planned

1. Character styles: inline runs carry a style name, with the same menu and a "Character style" section.
2. A `StyleHost` for creates (shapes; `fill` and `stroke` are already on the allow-list) and later for computes cells
   — until then the "shared" dialog of E5.13 is used by one app.
3. Delete and merge of styles (the E1.10 deletion rules) and the "to name" list as a view.
4. Style changes and locks; the style gallery's search and grouping.
