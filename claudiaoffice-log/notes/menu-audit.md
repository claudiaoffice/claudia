# Menu audit, phase 1: the workbook against the apps (2026-11-25)

Phase 1 of the menu work agreed on 2026-11-25. It only looks, nothing in the apps changed. It compares the menu workbook
`claudia-menus.xlsx` (version 6, the target) with what the three apps show today on `main` at `a5f5aa1`. Every
difference is one row on the workbook's new **Diagnosis** sheet, with **Decision** and **Your comment** columns for the
owner. Phases 2–5 (decide the gaps, design menus that show only what fits the context, rebuild the menus, switch on
dynamic menus) build on it.

## How it is made, and how to make it again

```
./run-e2e.sh setup                        # once: the built web app and a browser
uv run python scripts/menu_capture.py     # what the web client shows → .claudia/menu-audit/web.json
uv run python scripts/menu_audit.py       # the comparison → sheet Diagnosis (replaced; --dry-run prints counts only)
```

- **Desktop clients (Linux, Windows, macOS)**: read from the shared manifest
  (`clients/linux/src/claudia_shell_gtk/manifest.py`). The Linux client builds its menus from it. The Windows and macOS
  menus are generated from it, and `generate_menu.py --check` confirmed they are current for all three apps. The
  generated shortcut table (`generate_menus.py --check`) is current too.
- **Web client**: `menu_capture.py` starts a real server with all three apps. In each app:
  1. Ann (owner) makes a document and shares it with Eddie (editor) and Vera (viewer).
  2. Ann's menu bar is read, in English and in German, before anything is inserted (afterwards Undo would name what
     she did).
  3. Ann inserts a table (composes) and a Mermaid container (all three apps: the one object each app inserts without
     a file or a dialog).
  4. For each of the three, every menu and submenu is opened, and every place with a context menu is right-clicked:
     - computes: a cell, a row header, a column header
     - composes: a paragraph, the table
     - creates: the slide
     - all three apps: the object

     The paragraph and the cell are chosen where no object covers them.
  5. The context menus are read once more for Ann in German.

  It records what a person sees: labels, the shortcut shown beside them, separators, greyed entries.
- **Matching**: a workbook row is found in an app by its "Today's action id" (through the manifest). The web entry is
  paired with its desktop twin in this order:
  1. same place and words
  2. the only entry left in that menu
  3. the only entry with these words anywhere

  A row without an id (a new entry) is looked for by its words, so an entry that exists under another name or in
  another menu is not reported as "not built". Style names and the built-in shapes are document data, like any name a
  document holds, and are left out of the translation check.

## The picture

- **The menus are one product already, in two definitions.** All desktop clients come from one manifest and are in step.
  The web menus are built separately (`lib/document-menus.ts`, gone since slice 4 (D1644), and each workspace) and differ from the manifest
  in 18 places:
  - **6 are by design.** Quit exists only on the desktop. Apply Style is a flyout of the styles on the web but opens
    the page's popover in a shell (D301).
  - **6 are the shapes** Circle, Rectangle and Triangle (composes, creates). They are in the web's Edit menu but in no
    desktop menu, because the manifest treats the shape library as per-document data (its `creates()` docstring). The
    workbook makes them fixed entries, Insert ▸ Shape ▸ … (rows 30–32), so they come with the rebuild.
  - **6 are bug UX-94** below.
- **Most of the gap is rearranging, not building.** Across the three apps:

  | Finding | Count |
  |---|---|
  | Entry in the wrong menu | 54 |
  | Different words | 65 |
  | Capitalisation only | 34 |
  | Different shortcut | 16 |
  | Different order or separators | 10 |
  | Not built yet | 18 |

  Of the 18 that are not built yet, My role…, Quiet mode, Corkboard, Scrapbook, Citation…, Bibliography… and
  New page are features in their own right. The shape entries for computes are another.
- **Edit is as overloaded as the owner said.** Most of what leaves it goes to Insert:

  | App | Edit today | Edit in the workbook | Moves to Insert | Moves to Tools |
  |---|---|---|---|---|
  | computes | 20 | 10 | 7 | 1 |
  | composes | 16 | 7 | 5 | 1 |
  | creates | 19 | 8 | 6 | 2 |

  The rest of the gap is entries the workbook drops or does not list. In computes, Row ▸ Delete and Column ▸ Delete
  also move inside Edit, into Remove ▸.
- **The workbook needs 60 answers** (filter "Needs your decision" = yes):
  - its 8 open "To decide" items
  - one capitalisation rule for all 34 case-only labels: the workbook writes sentence case, the manifest header
    capitalisation, which the GNOME HIG asks for in menu items
  - one question: should the built-in styles and shapes be translated? They show in English in German, like any name
    a document holds.
  - a shortcut clash: Delete From Server… has Ctrl+Shift+Alt+R today, and the workbook gives that shortcut to
    Insert ▸ Shape ▸ Rectangle
  - rows 95 and 96, appended after their menus ended
  - 41 entries the apps have and no workbook row places. For most of them the workbook's own notes say they go (Save,
    the three ownership entries, Rotate ▸, Wrap Text, the table commands, Clear Cells, Edit Text, Delete); the sheet
    quotes the note, so these need only an "ok". Nothing in the workbook covers **Go to Target** and **Delete From
    Server…**. **Reference in Chat** appears only in a shortcut note ("Ctrl+Alt+X was Reference in Chat and is free"),
    which is not a decision.
  - one web-only entry (View ▸ Flow in composes)
  - context menus that have more than the workbook lists: the computes cell menu has 7 entries where the workbook names
    2 others; the computes row and column header menus have "Insert Row Above, …, Row height…" where the workbook says
    "Height / width…, Insert / delete ▸"
- **The workbook is behind the app in one place.** Insert ▸ Table (row 27) is marked "New" with Ctrl+Shift+Alt+T, but
  composes already has Insert ▸ Table… on Ctrl+Shift+F.
- **Context menus.** All three apps have the object menu, but without the workbook's Cut and Copy. A right press on a
  paragraph in composes opens the style popover, not a menu with Name & describe… and Style…. The composes table menu
  matches the workbook. A right press on the slide in creates opens nothing, and the workbook has no slide menu either.
- **Roles: the input for phase 3.**
  - 117 entries, in the menus and the context menus, are usable by the owner but greyed for an editor or a viewer.
    Share…, Assign New Owner… and Delete From Server… are greyed for both editor and viewer, and the editing entries
    for a viewer.
  - The reverse check found 10 entries a viewer can still use in Edit, Insert and Format: All Styles…, Colours…,
    Edit This Style… and List ▸ All Numbering…. Each needs checking whether it changes the document or only shows it.
  - View ▸ Replay History… is greyed for a viewer and View ▸ History and Chat is not. That fits D1261 (a viewer gets no
    history, and the panel says so). It is the kind of entry phase 3 has to settle: hide it, or keep it greyed.

## Phase 2, round 1: the owner's answers (2026-11-25)

The owner answered all 60 rows that needed a decision. The answers are D1607–D1615 and story E5.25. They are written
into the workbook as follows:

- **Diagnosis:** the answers are in the Decision and Your comment columns. `menu_audit.py` keeps them when it rebuilds
  the sheet, for every row that is still there.
- **To decide:** #14, #15, #17–#21 and #25 are answered "agree".
- **Menus and Context menus:** the new and changed rows are marked in their status column, and new cells are in blue.
  - Page View is one switch.
  - Tools ▸ Pivot table… is a single entry.
  - Select Next / Previous Object are in Edit; File ▸ Quit is a desktop entry.
  - Back where I was and AI… sit in their menus' order.
  - The new context menus are the reference's (Go to target), the pivot table's, and the row and column headers'.
  - Reference in chat is in every thing's context menu.
  - The computes cell menu is complete.

The rebuilt Diagnosis sheet has 439 rows. 29 of them need a decision, and all 29 carry the owner's answer: the work
they describe is still to do (one capitalisation rule, one question, View ▸ Flow, and 26 entries the apps have and the workbook
drops). Entries the workbook now places in a context menu are listed as "Moves to a context menu" (21). Renamed
context-menu entries are paired with their old words instead of being listed twice.

## Phase 2, round 2: the last open items (2026-11-25)

The owner settled the last open items, D1616–D1619:

- **The shortcut review (To decide #18).** All proposed shortcuts are confirmed. Format ▸ Style ▸ Edit… gets
  Ctrl+Shift+Alt+H, the last free letter of its block. Ctrl+Alt+X stays with Reference in chat; Ctrl+Alt+G, which
  the owner wanted for "go", is View ▸ Grid in creates.
- **macOS.** It gets its own shortcuts for Name & describe… (Cmd+Ctrl+N) and History & chat (Cmd+Ctrl+H), to be tried
  on a Mac. Its app menu lists Preferences ▸ (Shortcuts, AI…, App language ▸). D1616 replaces D1613.
- **Wording and order.**
  - An entry that opens a dialog ends with "…".
  - Insert ▸ Container ▸ is alphabetical.
  - In German a style is a "Formatvorlage".
- **Right press.** On a paragraph it opens the paragraph's context menu, not the style popover. On a slide it opens
  the slide's context menu, the same as its tab's.
- **"Fits when".** The column is accepted as filled.

The accepted proposals are no longer blue in the workbook. With this, the workbook is the complete target for the
rebuild (E5.23, E5.24); the decision range D1600–D1619 is used up.

## Bugs found (sizes 1 huge – 3 small)

| ID | Size | What |
|---|---|---|
| UX-94 | 3 | Logged in the tracker; the owner (2026-11-25): fixed later in this work, with the menu rebuild. Web and desktop disagree. Help ▸ About is "About claudia" on the web and "About Claudia Composes" (etc.) on the desktop (3). computes' Clear Cell Style sits inside Format ▸ Apply Style ▸ on the web but directly in Format on the desktop (1). composes' View has two entries, Flow and Page, on the web and one switch, Page, on the desktop (1). computes' Tools has Value Field Settings… and Pivot Fields in the opposite order (1). |

Seen in passing, already in the tracker: the German Undo reads "Rückgängig: Add container" once something was
inserted, because command names are not translated (CODE-31).

## What could not be run, or was not captured

- **Firefox**: Playwright cannot download it in this sandbox (the network allowlist blocks its download hosts). The
  capture ran in Chromium. The menus are Vue data, so their content does not depend on the browser, but how they look in
  Firefox was not seen.
- **The desktop clients themselves** (GTK on Linux, Neutralino on Windows and macOS): not run. They are compared through
  the manifest they are built from. The macOS app menu (workbook rows 92–94) is marked "Not checked".
- **Not captured yet.** The capture does not yet reach these places; nothing in the sandbox prevents it, the capture
  simply does not do them yet:
  - context menus of a list, a section header, sheet and slide tabs, the chart on a sheet, a paragraph in a text box,
    a table in computes, and composes' table headers
  - the entries of submenus that are greyed with nothing selected: Format ▸ Rotate (all apps), Format ▸ List
    (computes), Tools ▸ Row/Column/Sort (composes)

  Each is a "Not checked" row on the sheet.
- **Text boxes and images**: the object menu was read on a Mermaid container. It is the same menu for every object
  kind, but "Edit text" shows only where an object holds text.

## Assumptions

- The workbook's group numbers count separators within a top menu. Inside a submenu only the order is compared, since
  the workbook gives a submenu's entries the submenu's own group.
- The Web shortcut column is the shortcut for the web and the Linux client. Windows and macOS are only compared when the
  workbook gives them a shortcut other than the Linux one (none does today).
- An entry the workbook moves to a context menu or to "Keys without entry" is reported in the menus as "Not in the
  workbook" with the workbook's note quoted, not silently passed: the owner confirms each with "ok".
- Greyed entries were read with nothing selected. An entry greyed for the owner too is not compared between roles.
