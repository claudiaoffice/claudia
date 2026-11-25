# Menus that show what fits (2026-11-25)

The owner's idea, grilled on 2026-11-25 and decided in D1600–D1606: a menu shows only the entries whose action fits the
moment, in the top menus and in the context menus. Whether what does not fit is hidden or greyed is to be tried, so it
is one switch per reason. This note holds the design behind the decisions and the setup of the trial. The architecture
(where it goes in the code, the class diagram) is the next step and is not decided here.

## What was decided

| | Decision |
|---|---|
| D1600 | Every entry is shown only where its action fits; what does not fit is hidden or greyed, one switch per reason. No entry is exempt. |
| D1601 | "Fits when" is a rule of named conditions, joined by and. Several selected things must all fit. A role change applies at once. A new condition is added in one place. |
| D1602 | An action that needs one kind of selected thing lives in that thing's context menu, with its shortcut. |
| D1603 | The top-level menus never change. Separators and empty submenus collapse. A menu or a context menu with nothing left shows one greyed line saying why. An open menu stays as it opened. |
| D1604 | A shortcut of an entry that does not fit shows a notice naming the reason. Preferences ▸ Shortcuts lists every action with when it fits. |
| D1605 | The workbook gets a "Fits when" column, and a test holds the code to it. |
| D1606 | For the trial the switches are a developer setting, every reason starts at hide, an entry can be overridden on its own. The menu rebuild carries the rules from its first build. The ai is unaffected. |
| D1615 | More words for "fits when" (below, marked †), and what a viewer gets. |

## The words of "fits when" (D1601)

A rule is one or more conditions joined by "and". Each condition belongs to one reason, and the reason decides whether
an entry that fails it is hidden or greyed.

| Reason | Conditions (first list; it grows by decision) | Example of the "why" sentence |
|---|---|---|
| role | anyone · editor or owner · owner | Only an owner can share this document. |
| server | has the tool for LaTeX · Mermaid · Typst | This server has no LaTeX set up. |
| client | desktop only · web only | Quit is only in the desktop app. |
| document | has a pivot table · has a table · has more than one sheet or slide · is being presented · something to undo† · something to redo† · has something to refer to† · has random numbers† · a place to go back to† · has objects† | There is no pivot table here. |
| selection | a cell or range · text · an object (of a kind) · a table · a chart · nothing · something† · a list item† · a pivot table† · an object that holds text† · an object that can turn† · an object on the grid† · more than one cell of the table† · a merged cell† | Select an object first. |
| ai | the ai can really answer (a model is set up, local or a provider; not the scripted stand-in) | The ai is not set up on this server. |

Examples of whole rules:
- Share… = role: owner
- Delete pivot table… = role: editor or owner · document: has a pivot table · selection: a pivot table (and so in the
  pivot table's context menu, D1602)
- Insert ▸ Container ▸ LaTeX = role: editor or owner · server: has the tool for LaTeX
- Ask ai = ai: the ai can really answer

† added by D1615, from the first fill of the workbook's "Fits when" column.

A viewer (D1615) gets:
- History & chat; the panel tells her it is for editors.
- Ask ai: it acts with her rights, so it can only read and answer.

She does not get Who wrote what, Replay…, All styles…, Palette or All numbering…. How do I and Documentation fit nobody
until there is help (E13).

## The trial (D1606)

- One setting per reason: `hide` or `grey`, plus an override per action id: `show`, `grey` or `hide`. An override
  beats its reason.
- Where the setting lives:
  - desktop clients: a file beside their other settings
  - web: a URL parameter
- Every reason starts at `hide`. To compare, switch one reason, e.g. selection, to `grey` and work for a while.
- Things to judge in the trial:
  - how a changing Edit menu feels
  - Undo and Paste, which the owner chose not to exempt
  - a viewer's Replay History… (greyed today while History and Chat is not; D1261)
  - a screen-reader pass (BITV, D1603)

## What follows for the build (input for the architecture step)

- **One menu definition for every client.** The definition carries each action's rule. Today the web defines its menus
  apart from the manifest, which is the cause of UX-92. The audit and the decisions on the menu work agreed one
  definition.
- **The client works out what fits.** It knows the role, the selection, the document's state, the server's tools and
  the ai's provider from what the server already sends. The answer also goes to a native shell:
  - The shell contract's `action_state` grows a `visible` flag. This is an additive change, so contract v1 stays.
  - The Windows and macOS shells already rebuild their whole menu on each state change (`menu-actions.ts`), so leaving
    entries out is cheap there.
  - The Linux shell greys through GTK actions. Hiding an entry there is to be confirmed in the architecture step:
    GTK menus can hide an item whose action is off.
- **Every "why" sentence is translated** (`po/`), like every other text.
- **The audit (`scripts/menu_audit.py`) learns the "Fits when" column**, and its comparison becomes the test of D1605.

## Next steps

1. Fill in "Fits when" for every row of the workbook. Review it with the owner together with the Diagnosis sheet
   (phase 2).
2. Mock-ups: an emptied menu, an emptied context menu, the shortcut notice, Preferences ▸ Shortcuts with "fits when".
3. Architecture with a class diagram, then Gherkin scenarios. Both go to the owner for review before any code.
