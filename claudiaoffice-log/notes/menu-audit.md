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
  generated key table (`generate_keys.py --check`) is current too.
- **Web client**: `menu_capture.py` starts a real server with all three apps and makes a document in each as Ann.
  Ann shares it with Eddie (editor) and Vera (viewer). It opens every menu and submenu for each of them, and once more
  for Ann in German. As Ann it also right-clicks the places that have a context menu:
  - computes: a cell, a row header, a column header
  - composes: a paragraph, a table
  - creates: the slide
  - all three apps: an object, captured on a Mermaid container (the one object every app inserts without a file or
    a dialog)

  It records what a person sees: labels, the key shown beside them, separators, greyed entries.
- **Matching**: a workbook row is found in an app by its "Today's action id" (through the manifest). The web entry is
  paired with its desktop twin in this order:
  1. same place and words
  2. the only entry left in that menu
  3. the only entry with these words anywhere

  A row without an id (a new entry) is looked for by its words, so an entry that exists under another name or in
  another menu is not reported as "not built".

## The picture

- **The menus are one product already, in two definitions.** All desktop clients come from one manifest and are in step.
  The web menus are built separately (`web/app/lib/document-menus.ts` and each workspace) and differ from the manifest
  in 10 places. Six are by design: Quit exists only on the desktop, and Apply Style is a flyout of the styles on the
  web but opens the page's popover in a shell (D301). The other four, plus the web-only View ▸ Flow, are bug UX-91
  below.
- **Most of the gap is rearranging, not building.** Across the three apps:

  | Finding | Count |
  |---|---|
  | Entry in the wrong menu | 54 |
  | Different words | 65 |
  | Capitalisation only | 34 |
  | Different key | 16 |
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
- **The workbook needs 59 answers** (filter "Needs your decision" = yes):
  - its 8 open "To decide" items
  - one capitalisation rule for all 34 case-only labels: the workbook writes sentence case, the manifest header
    capitalisation, which the GNOME HIG asks for in menu items
  - a key clash: Delete From Server… has Ctrl+Shift+Alt+R today, and the workbook gives that key to Insert ▸ Shape ▸
    Rectangle
  - rows 95 and 96, appended after their menus ended
  - 41 entries the apps have and no workbook row places. For most of them the workbook's own notes say they go (Save,
    the three ownership entries, Rotate ▸, Wrap Text, the table commands, Clear Cells, Edit Text, Delete); the sheet
    quotes the note, so these need only an "ok". Nothing in the workbook covers **Go to Target** and **Delete From
    Server…**. **Reference in Chat** appears only in a key note ("Ctrl+Alt+X was Reference in Chat and is free"), which
    is not a decision.
  - one web-only entry (View ▸ Flow in composes)
  - context menus that have more than the workbook lists: the computes cell menu has 7 entries, the workbook names 2
    others; the computes row and column header menus differ from the workbook's "Height / width…, Insert / delete ▸"
- **The workbook is behind the app in one place.** Insert ▸ Table (row 27) is marked "New" with Ctrl+Shift+Alt+T, but
  composes already has Insert ▸ Table… on Ctrl+Shift+F.
- **Context menus.** All three apps have the object menu, but without the workbook's Cut and Copy. A right press on a
  paragraph in composes opens the style popover, not a menu with Name & describe… and Style…. The table menu matches.
- **Roles: the input for phase 3.** 91 entries are usable by the owner but greyed for an editor or a viewer. Share…,
  Assign New Owner… and Delete From Server… are greyed for both editor and viewer, and every editing entry is greyed for
  a viewer. View ▸ Replay History… is greyed for a viewer and View ▸ History and Chat is not. That is consistent with
  D1261 (a viewer gets no history; the panel says so), but it is exactly the kind of entry phase 3 has to settle:
  hide it, or keep it greyed.

## Bugs found (sizes 1 huge – 3 small; not yet in the tracker, the owner decides fix or log)

| Proposed ID | Size | What |
|---|---|---|
| UX-90 | 3 | The shape entries Circle, Rectangle, Triangle (Edit, composes and creates) are not translated: the German menu shows them in English. |
| UX-91 | 3 | Web and desktop disagree: Help ▸ About is "About claudia" on the web and "About Claudia Composes" (etc.) on the desktop. computes' Clear Cell Style sits inside Format ▸ Apply Style ▸ on the web but directly in Format on the desktop. composes' View has two entries Flow and Page on the web, one switch Page on the desktop. |

## What could not be run here

- **Firefox**: Playwright cannot download it in this sandbox (the network allowlist blocks its download hosts). The
  capture ran in Chromium. The menus are Vue data, so their content does not depend on the browser, but how they look in
  Firefox was not seen.
- **The desktop clients themselves** (GTK on Linux, Neutralino on Windows and macOS): not run. They are compared through
  the manifest they are built from. The macOS app menu (workbook rows 92–94) is marked "Not checked".
- **Context menus the capture does not reach yet**: lists, a section header, sheet and slide tabs, the chart on a sheet,
  paragraphs in text boxes, tables in computes, and composes' table headers. These are rows of kind "Not checked".
- **Text boxes and images**: the object menu was captured on a Mermaid container only. It is the same menu for every
  object kind, but "Edit text" shows only where an object holds text.

## Assumptions

- The workbook's group numbers count separators within a top menu. Inside a submenu only the order is compared, since
  the workbook gives a submenu's entries the submenu's own group.
- The Web key column is the key for the web and the Linux client. Windows and macOS are only compared when the workbook
  gives them a key other than the Linux one (none does today).
- An entry the workbook moves to a context menu or to "Keys without entry" is reported in the menus as "Not in the
  workbook" with the workbook's note quoted, not silently passed: the owner confirms each with "ok".
