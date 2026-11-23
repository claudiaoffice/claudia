# Penpot design file

`claudia.penpot` is the design system and screens of Claudia as one Penpot file (import it in Penpot).
`generator/` builds it from the running web app (`node build.mjs out/full.penpot`; needs the server running for text measuring).

Pages: Foundations, Icons, Components, Front page, Dialog components, Styles dialog, Search & replace,
**Workspace foundations**, **Workspace components**, **E6.31 Slides in computes** (the agreed designs of that story),
**Workflow components**, **E16 Corkboard**, **E16 Quiet mode**, **E16 Binder** (the agreed designs of the epic E16
Workflow: decisions D1101 to D1116 in claudiaoffice-log),
**AI provider components**, **E7.11 Server settings AI**, **E7.11 AI states**, **E7.11 Owners' consent**,
**E7.11 Chat panel** (the agreed designs of E7.11 "Claude as an AI provider"; the SVG mocks are
`claudiaoffice-log/notes/mockups/ai-provider-1` to `-4`).

Notes on the E16 pages:
- The screens of composes and creates take their colours from the App theme that is switched on (Config ▸ Themes ▸ App),
  like the rest of the file; as built they show computes. Switch the theme to see them in composes or creates.
- The toolbar under the menu bar is the one of the Slides screens, as there is no composes or creates toolbar in the file yet.
- Menu entries and key shortcuts are left out on purpose: the shortcuts of D1115 are to be reworked (many clash with existing keys).
- The E7.11 pages show the menu as "Preferences" (the story renames Config in all apps); the other pages still say Config
  until that rename is built. The read-only look of the consent dialog for editors and viewers (screen 3) is shown by
  its words only; the greyed check box is not drawn.
- Panels, docks and the hide handles are drawn in the real chrome of the workspace (the dark History & Chat panel);
  the light docks of the SVG mocks in claudiaoffice-log are the same designs.

The file is hand-corrected in Penpot, so a rebuild never replaces it. Add new pages to it with
`python3 generator/tools/extend.py out/full.penpot claudia.penpot out/new.penpot "Page" ...`:
it only adds pages, components, text styles and tokens that the file lacks, and leaves everything else as it is.

The ids of the shapes come from the order they are made in, so whatever is new is built after everything that is
already in the file, pages included. A new text style or radius would add a sample to Foundations (built first) and move
every id after it: such tokens are listed in `LATER` (`src/tokens.mjs`) and shown on a page of their own instead.
