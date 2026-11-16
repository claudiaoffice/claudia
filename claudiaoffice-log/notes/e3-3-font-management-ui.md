# Font management: where the front ends go — proposal, 2026-11-16

E3.3, E14, E1.9. Nothing in this note is built or decided. Mock-ups, to agree before any code:

- `mockups/fonts-1-server-settings.svg` — Server settings ▸ Fonts, the server's catalogue
- `mockups/fonts-2-add-fonts.svg` — Add fonts…: check first, then add
- `mockups/fonts-3-fonts-in-this-document.svg` — Format ▸ Fonts…, the fonts of one document
- `mockups/fonts-4-open-picker-add.svg` — the notice on opening, the style's font field, adding a font to a document

Added the same day, after the owner's answer below:

- `mockups/fonts-5-import.svg` — import: every font of the file and what stands in for it
- `mockups/fonts-6-while-working.svg` — while working: "Arial, shown as Liberation Sans"
- `mockups/fonts-7-export.svg` — export: each stand-in written back under its own name

PNGs with the same names. They replace the earlier canvas mock (Tools ▸ Font manager…, from the time when each app
had its own server).

## Where things stand (checked against the tree at `4b608aa`)

- **Built:** the catalogue `claudia-fonts` (collections with a licence record, problems, substitutions, WOFF2 cache);
  the public routes `GET /api/fonts`, `/api/fonts/{sha256}`, `/api/fonts/{sha256}.woff2` (D905); the starter set
  shipped inside the package and read before `--fonts` (D500); variable fonts (D911); the print preview names a
  family it replaced.
- **Not built:** any UI for fonts. The server settings have three pages (AI model, Typesetting, Access & documents);
  the style's font field (`StyleFontPicker.vue`) offers a fixed list in `lib/fonts.ts` (Georgia, Arial, Verdana …) that
  has nothing to do with the server's catalogue; `providable_fonts` is not in the manifest check, and
  `FontRequirement` holds a family name only, no hash; there is no per-document `fonts.lock`; documents cannot carry
  fonts; imports do not read embedded fonts from .docx or .odt.

## The proposal in one paragraph

Fonts have two homes, and each gets one front end. **The server's catalogue** is what every document on that server
is laid out with; it belongs to the administrator and lives in the server settings, as a fourth page beside
Typesetting. **The document's own fonts** are the ones its styles ask for, pinned by hash, and optionally kept inside
the sealed document like its images; they belong to the document's editors and live at Format ▸ Fonts…, in all three
apps. A person who lacks a font adds it *to the document*, not to the server, so no administrator is needed and the
document stays a self-contained box (the map/key/box picture of 2026-11-12). Only on a desktop client's own local
server, where the person is the administrator, can she add it to the server too, with one checkbox.

## Why this split

1. **One server, one catalogue.** Since D430 one server hosts the three apps, so a per-app font dialog under Tools
   (the earlier mock, and the memory of "one catalogue per machine") no longer has a reason. The catalogue is a server
   setting like the AI model and the LaTeX programs (D154), reached the same way.
2. **"Exactly the fonts it was written with" is a property of the document, not the server.** A server can only
   promise what it has; a document can carry what it needs. Pinning by SHA-256 (as the routes already address fonts)
   makes "as written" checkable; keeping the files inside the document makes it true on any server. This is also the
   only answer that survives a document moving between servers (export as .claudia, a colleague's server, ten years
   later).
3. **Adding a font must not need an administrator, and must not turn a shared server into a font-sharing site.** A
   font added to one document stays in that document; the font file's own embedding bits (OS/2 `fsType`) decide
   whether it may be added at all — the same rule Word and LibreOffice apply when they embed fonts.

## The pieces

### Server settings ▸ Fonts (board 1, 2)

- A page in `AdminShell.vue` between Typesetting and Access & documents, icon "Aa". Administrators only (D151).
- **Collections** as cards: Shipped with Claudia (always there, cannot be removed, D500), then what was added. Each
  card: families, licence, who added it and when; ⋯ holds Rename, Replace files…, Remove collection… (danger-zone
  confirmation naming the server and the families that go).
- **Families** as a table: the name set in its own face, styles, collection, *May go*, and what it stands in for.
  Filters: All, Stand-ins, Not usable. A family with a problem shows the reason in words and what is used instead.
- **Stand-ins** made visible (`Catalogue.resolve`); Edit stand-ins… for the administrator's own pairs, the shipped
  metric-compatible ones locked.
- **Add fonts…** is a two-step dialog: choose files (or fetch an open collection from a pinned list, checked by
  SHA-256, hidden on a server without network), name the collection, say who may receive the fonts, give the licence
  in words; then *Check files*, which shows one line per file (added, left out and why, replaces a shipped font, CFF
  outlines shown on screen only) and a confirmation that states the scope. Nothing on the server changes before that
  second step.

### Format ▸ Fonts… (board 3)

- In composes, computes and creates, beside Colours…, shortcut **Ctrl+Alt+E** (free in all three; Ctrl+Alt+F is
  Follow Computation in computes, Ctrl+Alt+T is the GNOME terminal).
- One sentence first: how many fonts are not as written, and which parts of the document that touches.
- One line per family the styles ask for: **status** (✓ As written · ✓ Kept · ≠ Other version · ≈ Stand-in ·
  ✗ Missing — a sign and a word, never colour alone), the family in its face, **used by** (the styles, since text has
  no direct formatting, D306; a style's name opens Edit This Style), **laid out with**, and actions: *Add font…*,
  *Replace…* (changes every style that names the family, one undoable command), *Use this version* (re-pins).
- **Keep the fonts inside the document**, with what that costs (size) and what it does to exports (kept fonts embedded
  in .odt and .docx where the font allows it).
- A link *Fonts on <server>…* for administrators.

### Where people meet fonts without asking (board 4)

- **On opening**, a one-line notice under the header bar, only when the page may differ from how it was written
  (Missing, Other version); same-width stand-ins stay quiet. Once per person and document. *Fonts…* opens the dialog.
- **The style's font field** lists only fonts a page can be laid out with: *In this document* first (with their
  status), then *On <server>*, each name in its own face, then *Add a font to this document…*. The fixed list in
  `lib/fonts.ts` goes. A typed unknown name is still accepted and shows as Missing.
- **Add a font to this document:** on the desktop clients, a list of this computer's installed families with their
  embedding status ("May be kept" / "Forbids it"), or a file; in the web client a file only (Firefox has no API to
  list installed fonts). On the client's own local server, a checkbox adds it to the server as well, into a collection
  "From this computer".

## What this asks of the model and the server

- `FontRequirement` gains the file's SHA-256 per style (and the axis values of D911), written when a style's font is
  set and when a document is imported; the manifest check compares by hash, which gives the five statuses.
- A document can hold font files (by hash, deduplicated, encrypted with the document like images), and the client's
  `FontSet` takes them from the document as well as from `/api/fonts`. The TeX path (D95) needs them too.
- Importers read embedded fonts: .odt `<style:font-face>` with `<svg:font-face-uri>` (LibreOffice embeds into
  `Fonts/`), .docx `w:embedRegular` etc. (obfuscated with the font key, ECMA-376 Part 1, 17.8.1). Exporters write them
  back for kept fonts.
- The licence record gets three answers instead of `redistributable: bool` (below), and the catalogue serves
  "This server" fonts to signed-in clients of that server only.

## Open questions for the owner

1. **Three answers for "may go"** — Anywhere / This server / Not usable — instead of the yes/no of D94? Without it a
   licensed house font (common in public administration, E12.7) can never be used, because only redistributable
   fonts reach a client today. "This server" fonts would then need the font routes to stop being public for them.
2. **Keep fonts inside the document by default?** Proposed: on, for new and imported documents. Cost: size (Inter and
   Fraunces with their italics are 2.5 MB; whole files, since a document being edited cannot use a subset); gain: the document looks the same everywhere and later. A lighter variant: fonts of the shipped set are only pinned, not kept, and become "Other version" on a server that ships a newer file.
3. **Users add fonts to the document, administrators to the server** — agreed? This is the main change against the
   earlier idea of users adding missing fonts "to the server through the desktop client".
4. **`fsType` as the rule for adding to a document:** installable and editable may be kept; preview-and-print and
   restricted may not. Microsoft's fonts (Calibri, Segoe UI) allow editable embedding, so a Windows user could carry
   Calibri inside her document, as Word does — consistent with "no Microsoft fonts in the starter set" (D93), which is
   about what Claudia ships, not about what a person embeds. Acceptable?
5. **Ctrl+Alt+E** for Format ▸ Fonts…?
6. **View ▸ Show Fonts Not as Written** (tint) — worth it, or is the dialog enough?

## Stand-ins made visible: import, work, export (owner, 2026-11-16)

The owner's experience moving between PowerPoint and LibreOffice Impress: decks from colleagues changed their look
completely because fonts were swapped silently, even by metric-compatible ones such as Liberation Sans for Arial. Same
widths keep the line breaks, but not the look. His request: keep the original name (an imported Arial stays Arial and
is exported as Arial), and make the temporary stand-in visible at three moments. Proposed (boards 5–7):

1. **Import.** A fourth step, *Fonts*, in the import dialog, shown only when a font of the file is not here as the file
   has it. One line per font: the name in the file, the stand-in in its own face with a sample, how close it is (*The
   same font* · *Same widths* · *Other widths*, with the slides or columns that break differently), and the way to the
   real font (*Use Arial from this computer* on the desktop clients) or a better stand-in.
2. **While working.** A quiet chip in the header bar, "≈ 3 stand-in fonts", only while any is in use; its popover lists
   the pairs ("Arial → Liberation Sans, same widths"), a switch View ▸ Show Stand-in Fonts (Ctrl+Shift+Alt+B, a dotted
   underline that is never printed) and Fonts…. Hovering text names its style and "Arial, shown as Liberation Sans".
   The style's font field shows "Arial  shown as Liberation Sans", and the font list gives every name with a stand-in
   a second line. Choosing Liberation Sans on purpose is different: the style then asks for Liberation Sans.
3. **Export.** The export dialog gets a *Fonts in the file* section: each font, what it is written as (the original
   name by default, or the stand-in embedded, "exactly what you saw here"), and what happens on the other computer,
   including where text fitted with a narrower or wider stand-in will not fit the same way. Open fonts and fonts the
   file carried are embedded where their embedding bits allow; Arial is not, as PowerPoint does not embed it either.
   Download of a kept original file needs no such section: its fonts are untouched.

The name already survives import: a style keeps the requested family first in its `font-family` (computes' importer
writes `Arial, 'Liberation Sans', sans-serif`, `cell_looks.font_family`), and substitution happens only at layout. What is new is that the resolver's answer (requested → provided, and how close)
becomes visible data for the UI, and that the import computes which slides or columns break differently.

## Proposed stories (after the mocks are agreed)

- E3.3a Server settings ▸ Fonts page and Add fonts… (server API: list collections, add with check, remove, stand-ins).
- E3.3b Fonts pinned by hash in the manifest; Format ▸ Fonts… in the three apps; the notice on opening.
- E3.3c Fonts kept inside the document; import and export of embedded fonts (ODF first, D70).
- E3.3d The style's font field from the catalogue; Add a font to this document (desktop: installed fonts; web: file).
- E3.3e Stand-ins made visible: the Fonts step on import, the header-bar chip and View ▸ Show Stand-in Fonts, the font field's "shown as", the export dialog's Fonts section.
- E3.3f Font sources: shipping metric-compatible open fonts (Arimo, Tinos, Cousine, Gelasio, Selawik) and fetching open fonts on demand; Microsoft's downloadable fonts on the desktop clients only.

Each needs the i18n strings in the `.po` catalog, keyboard shortcuts in the manifest, the native menus of the desktop
clients, and a BITV check of the dialogs (status in words, table semantics, focus order).
