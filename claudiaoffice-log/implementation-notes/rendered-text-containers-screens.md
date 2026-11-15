# Rendered text containers: the screens (branch `containers`, D560–D564)

What a person does, and where it is in the code. The engine and the wire are in `rendered-text-containers.md`.

## What is built

- **Insert ▸ Container ▸ LaTeX / Mermaid / Typst** in the web app of all three apps and in every desktop client (one
  menu manifest, `clients/linux/.../manifest.py`; the macOS and Windows menus are generated from it). Keys
  Ctrl+Alt+Shift+F, G, Y (`scripts/generate_keys.py` made `keys.generated.ts` and `notes/keyboard-shortcuts.md`).
  `insertMenu` in `web/app/lib/document-menus.ts`; the ids are written out there so the manifest test can find them.
- **One store of containers in the base session** (`web/app/lib/base-session.ts`): `renderTypes`, `renderings`,
  `renderOutcomes`, events `rendering` and `render_result`, `addRendering`, `setRenderingSource`. An older server
  without these methods opens as before. Pure helpers (fences, picture, status, words) in `web/app/lib/rendering.ts`.
- **Shared components** `RenderedFace.vue` (picture or why there is none; alert for failures, status for "Drawing…") and
  `RenderedEditor.vue` (monospace text, Ctrl+Enter or blur draws, Escape cancels, Enter is a new line).
- **Creates**: `SlideCanvas.vue` draws a container as a picture, opens the editor on double-click, Enter or F2, sizes it
  by the handles. `SlideSession.addContainer`, `fenceToContainer` (a finished text box that is one fenced block).
- **Computes**: `SheetGrid.vue` draws it in the floating-object layer; double-click, Enter or F2 edits.
  `Session.addContainer` anchors it to the selected cell.
- **Composes**: server wire `add_rendering` (block, offset), `move_object`, `resize_object`, `remove_object`
  (`claudia_server/composes.py`; `add_rendering_methods(..., guard=...)` refuses the assistant); `TextSession` keeps
  `objects` and `images`; `TextContainers.vue` draws the layer over the page (`lib/text-containers.ts` is the
  arithmetic); pasting a fenced block makes a container (`pasteFence`).
- i18n: new strings in `po/claudia.pot`, German in `po/de.po`, `web/public/i18n/*.json`, `claudia.mo`.

## Not built (follow-ups)

- Office export of containers from odt, docx, ods and xlsx (they write no objects yet; the export dialog has to
  report a loss "rendered-text"). ODP and PPTX already carry the picture.
- Typing the closing fence in composes does not convert; copy of a container as fenced text; a "Container settings…"
  dialog for the type's parameters.
- Composes: dragging a container to any place on the page, text wrap; moving Edit ▸ Insert (the hyphens) under Insert.
- Native Gtk menus for the Insert menu are in the manifest and tested there; they were not run on a display here.
- The mockups (`notes/mockups/containers-ui.svg`) were made before the build and not redrawn after it.
- Help topic for containers (EN/DE) and the Sphinx pages for the new wire methods.
- Excalidraw was left out (D564).
