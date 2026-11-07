# Claudia — Decision Log

Moved from the project context on 2026-11-05. Format: `ID · Decision · Date · Notes`. A decision is replaced, never
deleted: the old entry is marked *superseded by Dxx*. "Proposal" in a note means it is Claude's suggestion, not yet
agreed.

## Renumbering, 2026-11-05 (read this first)

Three documents allocated D-numbers independently and two blocks collided: `decision-log.md`, the Epic 2 container
design, and the Linux client notes each used **D70–D82** and **D97–D99** for different decisions. The collision was
live in the source as well as in the documents (`claudia_container/crypto.py` cites D74 meaning the cryptographic
primitives, while `claudia_server/composes.py` cites D75 meaning the styling details).

Resolved as follows: this log keeps the product numbering, because it was first and is cited most widely. The other
two blocks were renumbered into free space, and the mapping is kept here permanently so an old reference still
resolves. **The code has not been updated yet** — that is tracked as DOC-01 in `bugtracker.md`.

| Old number, in that document | Subject | New number |
|---|---|---|
| E2 design D70 | Threat model | **D100** |
| E2 design D71 | Key hierarchy | **D101** |
| E2 design D72 | User names not visible in the file | **D102** |
| E2 design D73 | Readable without a password | **D103** |
| E2 design D74 | Primitives: Argon2id, HKDF, AES-256-GCM | **D104** |
| E2 design D75 | Recovery key | **D105** |
| E2 design D76 | Write path: journal, group commit, one file | **D106** |
| E2 design D77 | New package `claudia-container` | **D107** |
| E2 design D78 | Unencrypted export and import | **D108** |
| E2 design D79 | Password rules | **D109** |
| E2 design D80 | What an encrypted download contains | **D110** |
| E2 design D81 | Viewers see the names of all users | **D111** |
| E2 design D82 | File extension `.claudia` | **D112** |
| Linux client D97 | Layout of the native clients | **D113** |
| Linux client D98 | Shell contract is a versioned JSON schema | **D114** |
| Linux client D99 | The Linux shell serves a local server | **D115** |
| Linux client D100 | Shell on 3.12, server on 3.14 | **D116** |
| Linux client D101 | Page adapter instead of changing the web app | **D117** |
| Linux client D102 | Rules of the web view in every shell | **D118** |
| Linux client D103 | The server never outlives its shell | **D119** |

## Vision

> Claudia is a privacy-first office suite of three quiet, elegant apps (composes, computes and creates) that you can
> run on your own hardware. Documents live on a server you choose, are shared live with colleagues, and an AI that runs
> where you decide works in the document as one more participant, bound by the same rules as everyone else. The
> interface stays out of the way and keeps its power in menus and context. The goal is to help people think with their
> data and ideas, not only record them.

Design character: a hint of female elegance, technical precision, technical power. Inspiration: Bret Victor
(co-thinking, understanding through interaction, visualization and simulation).

A proposed addition about stories across the three apps is in `notes/product-vision.md`; it is not part of the
statement until the owner agrees.

## Product and UX

| ID | Decision | Date | Notes |
|---|---|---|---|
| D1 | The suite is called **Claudia**, with three apps: *composes* (text), *computes* (tables, Excel-like), *creates* (presentations). | 2026-11-01 | Name is close to "Claude" (accepted knowingly). Not yet checked for trademark or existing products. |
| D2 | Each app is separately installable: its own doc server, a GTK desktop client and a web client. A fourth, shared AI server serves all three. | 2026-11-01 | The AI server can be scaled up (for example when cloud-hosted). |
| D3 | The UI follows GNOME 50 HIG and is recognisably a GNOME app. The desktop client runs on GNOME/Linux, Windows 10+ and macOS. Web and desktop clients are as similar as possible in where buttons and bars are placed. | 2026-11-01 | Cross-platform confirmed as really important (D22). Refined by D42 and D44: the GNOME identity holds on Linux; Windows and macOS get a web shell with the OS title bar and menu. |
| D4 | Menus are header-bar menu buttons: **File, Edit, Tools, Help**, identical on desktop and web. Tools holds app-specific items. | 2026-11-01 | File: Open, Save, Save As, Exit. Edit: Undo, Redo, Cut, Copy, Paste, Paste As (Undo and Redo by D54, Cut by D74). Help: Help, About. **Open:** where the demo's Insert items go. Refined by D44. **Not held today:** the web app has six menus and the Linux shell maps between them (UX-06, UX-09). |
| D5 | **Open** creates a new document on the server or opens an existing one. **Save** creates a checkpoint. **Save As** downloads to the client in Claudia native, MS Office or OpenDocument format. | 2026-11-01 | Native plus one open format per app first. Open shows the documents of the server (D53). The first format family is OpenDocument (D70). |
| D6 | The AI user is named `ai`. The app design is impersonal about the AI; what the model says about itself is the model's choice. | 2026-11-01 | Only one `ai` per document and session. |
| D7 | The AI and history/chat box is integral to the workflow but can be shrunk or hidden and brought back with one click or a key sequence. | 2026-11-01 | Refined by D40: docked on the right, not floating. |

## Architecture

| ID | Decision | Date | Notes |
|---|---|---|---|
| D8 | The doc server always initiates the connection to the AI server. | 2026-11-01 | The AI server needs no knowledge of which documents exist. Not built: the AI runs in process today. |
| D9 | The AI server has separate skill files for each app. | 2026-11-01 | Refined by D24. |
| D10 | A shared package **claudia-core** is used by all three doc servers. | 2026-11-01 | Refined by D45–D50: the kernel is `claudia-core` (stdlib only, guarded by a purity test); the network layer is its own package `claudia-server`. |
| D11 | Presence is similar in composes and computes. In composes each person's cursor is shown and a zone around it is locked: **± n words**, with n configurable. | 2026-11-01 | Built as `look` and `hold` with ± 3 words. Open: word definition, lock release, behaviour at boundaries. |
| D12 | The formula language is meant to be Microsoft Excel's. The function library grows step by step, using the UserFunction mechanism as far as possible. | 2026-11-01 | **Exactness is deferred (D23).** Open: locales, dynamic arrays, date system, rounding. |
| D13 | The AI hardware is configurable. OpenVINO is the primary runtime, GPU the default device. | 2026-11-01 | `openvino-genai` 2026.4.1 publishes cp314 wheels. Never run against a real model. |
| D14 | The licence is as close to GPL as the used components allow. Decided per component as we go. | 2026-11-01 | |
| D15 | The **command log is the source of truth** of a document. Checkpoints (Save) are labels on revisions. Snapshots are only caches. | 2026-11-01 | Storage and encryption: D19–D21, D34, D100–D112. |
| D16 | All doc servers are written in **Python**, using C-backed libraries where performance matters. The interpreter is **always bundled** with the installers. | 2026-11-01 | Performance design: D36, D37. |
| D17 | A **Region** is the common abstraction for presence, locks and AI edits: a cell range in computes, the ± n words window in composes, an object or set of objects on a slide in creates. | 2026-11-01 | Built: `CellRegion`, `TextRange`, `ObjectSet`, `Interval`. |
| D18 | The claudia computes demo is the backbone and reference; reuse as much as is possible and useful. | 2026-11-01 | Its two signature features: Python extensibility (UserFunction) and SQL on named ranges. |

## Common to all three apps

| ID | Decision | Date | Notes |
|---|---|---|---|
| D19 | Claudia's own format is **JSON-based, zipped and by default encrypted** with a user-provided password. MS Office and OpenDocument are import/export only. | 2026-11-01 | ZIP is only the container; entries are encrypted with our own scheme (D34, D100–D112). ZIP's built-in AES is not usable (PBKDF2-SHA1, 1,000 iterations, and `zipfile` cannot write it). |
| D20 | **Passwords belong to the document, not the user.** There is no central user management or user database. | 2026-11-01 | Users are entries inside the document (D35). Revoking access for copies already handed out is impossible. |
| D21 | **Command schemas are versioned** (also for UserFunction/plugin extensions). **Redaction of history must be possible.** | 2026-11-01 | Redaction does not reach copies or backups made earlier. Open: what a redaction leaves in the log. Not yet true of the container (SEC-05). |
| D22 | **Cross-platform desktop** (GNOME/Linux, Windows 10+, macOS) is a hard requirement. | 2026-11-01 | The replacement for web content is D41; the shells are D42. |
| D23 | The computes core can call **fast plugged-in computation functions**. **Lookup and reference functions stay in the core** for efficiency. Excel-exactness is not a concern for now. | 2026-11-01 | Built as `formula/forms/` (core) and `functions/library/` (UserFunction). |
| D24 | The AI stays a placeholder for now. Each of the three apps gets its own **skills.md and persona.md**. | 2026-11-01 | The skill files do not exist yet. |
| D25 | The demo's GUI is reworked to the agreed menu structure (D4). | 2026-11-01 | |
| D26 | A **font library** lives on the server as a service shared by the three servers: the OS fonts plus downloadable collections. A document declares the fonts it needs; the server delivers fonts the client lacks. | 2026-11-01 | Built as `claudia-fonts`; not yet wired to the server. Fonts are served from our own server, never a CDN. |
| D27 | GTK layout lives in **XML files** (GtkBuilder), not in code. | 2026-11-01 | Held: `clients/linux/src/claudia_shell_gtk/data/window.ui`. |
| D28 | One good-looking **About dialog** shared by all apps, showing each app's own logo icon. | 2026-11-01 | Built by hand on `Adw.Dialog` in the Linux shell, not `Adw.AboutDialog` — its own Website/Troubleshooting/Legal row is oversized next to the web app's buttons (owner's report, 2026-11-06); a shared web component elsewhere. Both sides read the same three links (Website, Report an Issue, Legal) in the same order (`manifest.py`'s `about_links()`, `AboutDialog.vue`'s `LINKS`). Patch exists, not yet committed (PROC-03) — see `notes/e5-1-e5-10-menus-and-accessibility.md`. |
| D29 | Every app server offers the **UserFunction** interface: users define their own functions or macros in Python. | 2026-11-01 | Who installs them: D38. Open: the macro API for composes and creates. |
| D30 | Every UserFunction has **getTooltip and getHelp** methods returning renderable help text in **LaTeX**. The user doc and help system is based on this. | 2026-11-01 | Built as a mandatory description plus at least one `Example` in `functions/base.py`. The LaTeX help text and the help system are not built. Widened by D88. |
| D31 | English first, **internationalization built in** from the start: every menu item and text is translatable. | 2026-11-01 | Proposal: gettext `.po` as the single source. **Not started:** no catalogue exists anywhere. |
| D32 | Every app server has **multi-user collaboration**. The command history is the track-changes feature by default. Users chat with `@<username> <message>`. One user can be the agentic AI `ai`. | 2026-11-01 | Remote model APIs send document content off the server: needs explicit opt-in and a visible indicator. |
| D33 | **claudia computes**: classical Excel-like functions with more elegance, user-friendliness and hidden power. Fields: project management, financial modelling, sciences, data analysis and interactive visualization, education and simulation. Inspired by Bret Victor. | 2026-11-01 | The Bret Victor features (sliders, what-if, dependency views) are not built. |

## Security, calculation and extensibility (second round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D34 | Encryption defends against **outsiders holding the file** and against **co-editors** who must not see parts of the history or chat. | 2026-11-01 | Design: key slots per password; keys per domain (content, history, chat); commands in blocks, compressed then encrypted; redaction rewrites a block. The server sees plaintext only while a document is open. Detailed by D100–D112. |
| D35 | **Users live inside the document**: each has a name, their own password and a role. | 2026-11-01 | Built: `people.bin` inside the container. `ai` stays a protected name. |
| D36 | **Calculation happens on the server.** Clients display values and keep no calculating replica. | 2026-11-01 | Cost: every edit needs a round trip; slider drags on a remote server must coalesce. |
| D37 | **Performance architecture:** incremental recalculation with a persistent dependency graph; the output range of a function is owned by it; inputs are not locked (a worker computes on a copy at revision r and its result is discarded if the inputs changed); results of worker functions stored in the log as commands with final values; two tiers (core and quick vectorised inline, heavy or slow in warm workers with timeouts); the kernel stays free of I/O; dragging uses an unlogged what-if preview; cells get a "calculating" state. | 2026-11-01 | The incremental graph is built (`calc.py`). **The worker tier is not**: everything runs on the event loop. |
| D38 | **UserFunctions are installed by the server admin** in version 1, from a folder on the server, and run in workers. A document declares what it requires (name, version, digest), like fonts. On a localhost setup adding a function must be really simple. | 2026-11-01 | Same trust rule everywhere: whoever controls the server's folder controls the functions. No executable code travels inside documents. |

## Repository (third round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D39 | The project lives in **one monorepo**. | 2026-11-02 | Each app and the AI server stay independently installable and releasable (D2). |

## Web views and the panel (fourth round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D40 | The **history and chat panel is docked on the right edge of the window**, in every client. An arrow on its left border shows or hides it; a key sequence does the same. | 2026-11-02 | Refines D7. At narrow widths it must push the content aside, never overlay it. Open: default width, remembered state, the key sequence. |
| D41 | **Partly superseded by D42.** Web content in the desktop client is shown by the **system web view of each OS**: WebKitGTK 6.0 on Linux, WKWebView on macOS, WebView2 on Windows. No browser engine is bundled. | 2026-11-02 | Why: small installs. Considered and dropped: bundled Chromium, a self-maintained Windows WebKit port, Servo, native chart drawing, server-rendered SVG. Reasons and sources: `notes/e0-shells-and-web-surface.md`. |
| D42 | The desktop clients are **thin shells around one shell-agnostic Nuxt frontend**. Everything inside the window is web content. **Linux: GTK 4 with libadwaita and WebKitGTK 6.0. Windows and macOS: a web shell around the system web view; Neutralino is the candidate.** A small **shell contract** (a JSON bridge) defines what a shell offers. | 2026-11-02 | Supersedes the plan of a GTK client on all three OSes and the embedding part of D41. Risks: Neutralino's maturity, Wayland, input methods and accessibility are **not verified**; the adapter must stay thin so Tauri or pywebview can replace it. |
| D43 | The desktop clients **bundle the frontend** and load it from the local package, never from a remote server. | 2026-11-02 | A shell's native API must only be reachable from bundled content. Servers must accept older frontend protocol versions; how old is open. Qualified by D115: the Linux shell lets its own local server serve the bundled frontend, so page and socket share an origin. |
| D44 | On **Windows and macOS** the shell uses the **OS title bar and the OS-native menu**, generated from the shared menu and action manifest. The structure File, Edit, Tools, Help is kept. On Linux the GTK shell shows it as header-bar menu buttons. | 2026-11-02 | On macOS, About, Preferences and Quit belong in the application menu, and Edit needs the standard Cut, Copy and Paste items for the shortcuts to reach web content. |

## Kernel and server (sixth round)

Details: `notes/e1-kernel.md`.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D45 | **Revision identifiers are `(branch, seq)` with a parent link**, not content hashes and not bare integers. | 2026-11-02 | Sequence numbers continue along a branch from its fork point; redaction never changes an id; no tamper evidence from the id itself. |
| D46 | **Undo is per author and never overwrites a colleague.** If a colleague wrote the same region after my step, my undo is refused (`UndoConflict`) and nothing is consumed. | 2026-11-02 | Implemented by `Command.shifted_by`: the stored inverse is moved through everything that ran since; `None` means "changed by somebody else". |
| D47 | **`execute` enforces locks for everybody, the `ai` user included.** A command that touches a region a colleague holds is refused (`RegionHeld`, code `locked`) and changes nothing. | 2026-11-02 | Undo checks the same rule. `check_free` stays public so a UI can ask in advance. |
| D48 | **Restoring a checkpoint forks.** The document continues on a new line `restore-N`; the old future stays under its unchanged revision ids on a hidden side line until an owner discards it. **`switch_to` is the way back.** Nothing is ever truncated. | 2026-11-02 | Locks and presence are cleared; views get `BranchSwitched` and `Rebuilt`. Rules for a live session: D51, D52. |
| D49 | **An edit made against a view that is no longer on the active line is refused** with `StaleEdit` (code `stale`) and changes nothing. | 2026-11-02 | `Document.execute(command, base=revision)`; the server's `apply` takes `base`; clients reload and try again. |
| D50 | *Proposal; the listing part is **superseded by D53**.* **Server access:** credentials travel in the first WebSocket frame, never in the URL; name plus password per document; the first person who asks for a document that does not exist becomes its owner; a wrong password, an unknown name and a missing document give the same answer; the name `ai` is refused; TLS by default with a self-made certificate whose fingerprint the client trusts like an SSH host; a browser page from another origin is refused unless named. | 2026-11-02 | With D53 the "same answer" rule can only hold for documents that are not listed. |

## Live sessions (seventh round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D51 | **Restoring a checkpoint in a live session needs the consent of everybody who is editing.** Any editing user may propose going back to checkpoint X; all other editing users get a banner asking for consent; only if all agree is it restored, and the old history stays on the hidden side line (D48). Someone who is not present is not asked. A **later feature** lets users see the lines and pick one. | 2026-11-02 | Refines D48. The kernel can already restore, list lines and switch; the consent flow and wire methods are E3.7, the line picker E3.8. Details: D52. |
| D52 | **Details of the consent flow.** (1) *Who is asked:* connected owners and editors. Viewers are told, never asked, never block. `ai` is never asked and never blocks; its running jobs are cancelled or marked stale. A sole editor restores at once. (2) *How a vote ends:* any "no" ends it; one open proposal per document; the proposer may withdraw; an unanswered proposal expires after a fixed time (two minutes to start with). (3) *Coming and going:* someone who disconnects is no longer asked; an editor who connects is added and asked. (4) *Work during the vote:* editing continues; on restore, edits in flight are refused with `stale` (D49) and the banner offers to copy what was refused; locks and presence are cleared. (5) *Switching back to a hidden line* follows the same flow. (6) *Users who were away* get a notice on return. | 2026-11-02 | The two-minute expiry is a starting value. Implementation: E3.7, not started. |

## Menus and documents (eighth round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D53 | **The server lists its documents.** File ▸ Open shows the documents on the server; the client does not have to remember document ids. | 2026-11-02 | Reverses the "no endpoint that lists documents" part of D50. What the list shows and to whom is settled by D103. |
| D54 | **Undo and Redo are in the Edit menu**, in all three apps and every shell. | 2026-11-02 | Refines D4. Cut was added by D74. |

## Demo v0 (ninth round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D55 | **The owner of a document lets people in through the `add_user` protocol method** (name, password, role editor or viewer). Owner only; the name `ai` stays refused. | 2026-11-02 | *Claude's addition for the demo.* It is the wire form of E2.3; the container's directory has replaced the stand-in behind it. A role still cannot be changed without removing and re-adding the person. |
| D56 | **The demo's AI is a scripted stand-in** behind the pluggable `Engine` interface. It is a real participant: a connection named `ai`, one per document, it hears `@ai`, answers privately, shows a cursor and a typing indicator, and edits through the same method table as everybody, so locks and roles apply to it (D47). | 2026-11-02 | The real model replaces the engine without client changes. The remote boundary of D8 is not built. |
| D57 | **Scope of demo v0** (web app, computes): list of documents and open/create, grid, formula bar, undo and redo, history and chat panel docked right with `@name` mentions, presence outlines and locks, checkpoints, the four menus, reload on `branch`/`rebuilt`/`stale`, a reconnect banner, the stand-in AI. | 2026-11-02 | Formulas, encryption and the container have since been built; the restore button still needs E3.7. |

## Stories across the suite (tenth round)

Reasoning and the owner's own pictures: `notes/product-vision.md`.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D58 | **The three apps work together to tell stories in different formats.** A spreadsheet that simulates something, a text that explains the background, a presentation that summarises the results and tells the arc from inspiration to insight. Moving insights between the apps must be truly easy. Users are not pushed into specific ways of thinking. The story is told and developed with critical thinking. | 2026-11-02 | How apps exchange material: D65, D72. |
| D59 | **Goal, plan and work evolve together, with immediate feedback.** | 2026-11-02 | *Refined by D71:* not a mandatory brief; goal, audience and stage are optional document metadata. |
| D60 | **Process help is offered in composes and creates and is always optional.** Composes: draft, then writing, then polishing. Creates gets the same kind of help. The user is not required to follow the phases. | 2026-11-02 | *Refined by D71.* |
| D61 | **Composes is a Word stand-in for polished documents.** Reports, letters, scientific and technical texts with formulas, meeting notes, drafting together. **Flow is the default view; the page view is a switch in the main editing window.** There is no separate print dialog or overlay. | 2026-11-02 | Built, though the page view is approximate: a sheet with margins, no real breaks, no headers or footers. |
| D62 | **Styles first**, in composes and creates. Every marking or style difference serves a purpose the user can name. When a style has no name yet, the user is invited to name it. In creates, templates and style definition come first, content separated from form as in LaTeX. | 2026-11-02 | *Refined by D73:* a deviation from a style becomes a new style with its own name. |
| D63 | **Edits by the AI are suggestions** that a person reviews. People's contributions in live collaboration are **immediate**. Each contribution should be identifiable by the user it came from. | 2026-11-02 | Built in composes (`suggest`, `accept_suggestion`, `reject_suggestion`) and in the authorship runs. **The guarantee is incomplete:** the generic `apply` method is not closed to the assistant (SEC-10). |
| D64 | **The AI is a thinking aid.** Composes: spelling, word choice, complicated wording, language style; later structure and flow; summaries and content proposals on request. Creates: cluttered slides, poor word choice, spelling, structure, and design choices. | 2026-11-02 | A scripted stand-in does the composes half; the rest is not built. |
| D65 | **The apps exchange material by documents on the server disk.** | 2026-11-02 | *Meaning settled by D72:* the person's client mediates and the material carries provenance. |
| D66 | **LaTeX formulas and Mermaid diagrams are supported in all three apps.** | 2026-11-02 | Rendered output is always an image, never inline. Widened by D88. |
| D67 | **Creates uses few shapes** (inspiration: Beamer; it is not a drawing program). Track changes records objects added and removed and text edited in them. **Marking a shape or text box locks it for other contributors.** Creates accepts all kinds of figures and images, and imports and exports **PPTX and ODP**. | 2026-11-02 | SVG from outside must be treated as an image, never inline. |
| D68 | **Slides come from a template, and the user must never be unsure where a slide comes from.** The PowerPoint master-slide confusion is the thing to avoid. Creates also takes up Prezi's idea of connected thoughts and storytelling. | 2026-11-02 | The owner is not sure how the user should work with templates; a mock-up is wanted before E10.4 is `ready`. |
| D69 | **Claudia is also for public administration and schools,** besides scientific users. The project wants to contribute to an open-source push for public organisations. | 2026-11-02 | Consequences: open formats first, accessibility, plain-language help, official templates, self-hosting. The accessibility half is the weakest part of the product today (UX-01 to UX-05). |

## Answers to the vision round (eleventh round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D70 | **OpenDocument is the first interchange family** for all three apps: **ODT, ODS, ODP** come first; docx, xlsx and pptx follow. **Claudia's own format stays**: zipped JSON with history, users and chat. | 2026-11-02 | Open-format exports contain the current state only, no history or chat. **Not started:** no import or export code exists. |
| D71 | **Goal, audience and stage are only suggestions and at most document metadata.** A user does not have to follow suggested phases or always have a goal. One option is offered: **"What would you like to achieve with this document?"** | 2026-11-02 | Replaces the mandatory-brief proposal. The metadata belongs in the encrypted content domain, not the plain manifest, because a goal can be sensitive. |
| D72 | **Material moves between apps through the person's client, with provenance, and is updated only after asking.** An embedded item records document id, server, range or chart name and source revision. When the source changed, the author is asked; nothing changes unless she accepts. | 2026-11-02 | No server-to-server trust, no shared keys. Not built. |

## Styling and Edit menu (twelfth round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D73 | **Styling is CSS in all three apps, in the file format as well as on screen.** In every client the person gets the same dialog for styling text or background. Cells in computes use **CSS table properties**. **Styles have names that express what they are for.** The dialog **starts with choosing a style**; deviating from it creates **a new style with a new name**. | 2026-11-03 | Refines D62 and D68. The command log stores style definitions and changes as commands. Details: D75. Built for paragraph styles in composes. |
| D74 | **Cut, Copy and Paste are in the Edit menu**, in all apps and all clients. | 2026-11-03 | Refines D54 and closes the Cut question D44 raised for macOS shortcuts. Select All is still open. |
| D75 | **Details of styling, accepted as proposed.** (1) a defined, versioned allow-list of properties and value types; no `url()`, no `@import`, no `@font-face`, no external references, no scripts. (2) Number and date formats, page layout and slide layouts are **not** CSS and have their own definitions. (3) A deviation creates the new style at once under a provisional name derived from its parent and puts it in the "to name" list, so naming never blocks typing. (4) A new style stores only its differences from its parent; changing the parent changes the child where it has not overridden. (5) Named styles map to named ODF styles; every export lists what could not be mapped. (6) One shared dialog: style picker first, then "Change this style…" and "Deviate…". | 2026-11-03 | Built as `claudia_core.css` (`CSS_VERSION` 1) and `claudia_core.styles`. The allow-list v1 is wider than the first proposal: padding and per-side borders are in, plus `fill`, `stroke`, `stroke-width` for shapes. Open: deleting a style that other styles are based on. |

## Help system (thirteenth round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D76 | **The help system is a knowledge base of short, example-oriented "how do I" topics, not an encyclopedia.** (1) the `ai` user has access to it as its knowledge base; (2) every extension brings its help; (3) help in context, while trying to use a feature. | 2026-11-03 | Refines D30 and D29. **Not started**, apart from one draft topic shipped with `claudia-typeset` (D99). |

## Claudia creates, first draft (fourteenth round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D77 | **Scope of the creates first draft:** slides with text boxes and shapes that can be added, selected, moved, resized, edited and deleted, with undo and redo; the docked panel; presence and locks; the four menus. **Not in it:** an AI participant for creates, images, templates and layouts, presentation mode, ODP and PPTX, multiple selection, copy and paste of objects, reordering, a style dialog. | 2026-11-03 | Follow-ups: E10.13. |
| D78 | **Shapes are JSON files in a shape library.** Format version 1: `format`, `id`, `name`, `path`, optionally `aspect` and `text_area`. The `path` is a string of absolute `M`, `L`, `C`, `A`, `Z` commands in a 100×100 box with a strict grammar. A library is a folder; a later folder replaces a shape of the same id; a bad file is skipped and listed at start-up. | 2026-11-03 | The owner asked for JSON everywhere: the file is JSON; only the outline is a path string, because a path of hundreds of numbers is unreadable as nested arrays. |
| D79 | **A document carries the definitions of the shapes it uses.** The first time a shape is placed, its definition is copied from the library into the document in the same history step. Opening never needs the library. | 2026-11-03 | Same idea as fonts and functions declared by a document, but embedded because a shape is a few hundred bytes. |
| D80 | **Every object refers to a named style; there are two built-in styles, `body-text` and `plain-shape`, and no style dialog yet.** The allow-list of D75 gains `fill`, `stroke` and `stroke-width`. | 2026-11-03 | Nothing on a slide has direct formatting. The built-in styles are in code, so a release that changes them restyles old documents — debt until E1.10 puts styles in the document. |
| D81 | **A new presentation starts with one slide, `s1`; ids of slides and objects are chosen by the server, random and never reused.** | 2026-11-03 | Two clients opening an empty document at once must not both create the first slide. Never reusing ids means an undo of a removal cannot collide with something added later. |
| D82 | **Selecting an object holds it** (a lock on an `ObjectSet`): the holder sees handles, others see her coloured outline and name tag. **Editing text:** double-click opens a plain-text editor, the box stays locked, Enter or leaving commits, Escape cancels. Moves and resizes are previewed locally and sent as one command on release. | 2026-11-03 | Others do not see a drag live, only its result. Plain text only until composes' inline marks exist. |
| D83 | **The slide has a fixed space of 1600 by 900 whole units (16:9); the least size of an object is 20.** The web view draws it in screen pixels, so strokes keep their width at every zoom. | 2026-11-03 | Other slide formats belong to templates. |
| D84 | **A server hosts one app, and the list of documents says which.** `GET /api/docs` returns `{app, documents}`. A `DocumentProvider` therefore has an `app`. | 2026-11-03 | Breaking for provider implementations. The web app has a shared `DocumentSession` and `DocumentFrame`. |
| D85 | **No AI participant for creates yet.** The panel and chat are there and `@ai` is answered as for any document without an engine. | 2026-11-03 | |

## Bibliography and full LaTeX (fifteenth round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D86 | **Composes has bibliographic support.** A **plugin** communicates with reference manager applications, for example Zotero or Mendeley. **The internal representation of bibliographies is BibTeX.** | 2026-11-03 | BibTeX has no formal standard. Entry types, fields and text storage are open. Not started. |
| D87 | **Composes imports and exports LaTeX,** in addition to OpenDocument and Microsoft formats. **Creates exports to LaTeX with the Beamer class.** | 2026-11-03 | Import of arbitrary LaTeX cannot be complete: unknown constructs are kept as raw LaTeX blocks. Not started. |
| D88 | **Full LaTeX support is part of the core,** so that all three apps can render formulas and beautiful text. | 2026-11-03 | *Claude's reading, accepted:* "the core" is the shared core of the suite, a service package used by the three servers, not the stdlib-only kernel. Confirmed as D89. |

## Fonts and typesetting services (sixteenth round)

Details: `notes/e3-fonts-and-typesetting.md`.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D89 | **`claudia-fonts` and `claudia-typeset` are packages outside the stdlib-only kernel.** `claudia-typeset` depends on `claudia-fonts`; both are under the API snapshot rule. | 2026-11-03 | Confirms Claude's reading of D88. |
| D90 | **Platform scope of the first version: a Linux server, also in Docker.** | 2026-11-03 | ***Superseded in part by D97 and D98:*** the sandbox now runs on Windows, and nothing is bundled: LaTeX is the user's own install. |
| D91 | **The engine is TeX Live, behind an `Engine`-style seam**; Tectonic is compared in E0.4. | 2026-11-03 | The full-document and biblatex questions of E0.4 stay open. |
| D92 | **The typesetting API is authenticated wire methods** (submit, status, cancel), not an open HTTP endpoint; **v1 uses its own small subprocess runner** behind `run_sandboxed`, which the worker pool of E3.5 replaces later. | 2026-11-03 | Fonts for browsers are the exception: public, immutable, behind the host guard. **The wire methods do not exist yet.** |
| D93 | **One font catalogue is the single source of truth for the engine and the browsers.** The same bytes are served as WOFF2 and shown to the engine. **Starter set** fetched through a lockfile; **no font binaries in git; no Microsoft fonts.** | 2026-11-03 | The lockfile and `claudia-fonts fetch` are not built. |
| D94 | *Assumed, not answered:* (1) **XeLaTeX is the one engine for all modes** in v1; (2) **every font collection has a mandatory licence record**, and a font is served to browsers only if its collection is redistributable; (3) **the fonts of the TeX trees are registered as a catalogue source by the server at start-up**. | 2026-11-03 | Change them if wrong. (2) is what makes the licence audit possible per font. |
| D95 | **Font substitution is applied by `claudia-typeset` in the TeX source, from `Catalogue.resolve`, not by fontconfig.** | 2026-11-03 | *Finding, not a choice:* XeTeX with fontspec ignores fontconfig `<alias>` and `<match>/<edit>`. |
| D96 | **Sandbox and output rules of the typesetting library:** `-no-shell-escape`, `shell_escape=f`, `openin_any=p`, `openout_any=p`, a private job folder as `HOME`, a clean environment, no input, rlimits, a wall-clock limit, a process group killed whatever happens; documents may bring only data files, never class or package files; the SVG is accepted only if it passes an allowlist with no script, no outside reference, no DOCTYPE; results cached by job, engine version and catalogue digest, failures never. | 2026-11-03 | Each rule has a test that fails when the rule is removed, checked by mutation for the sandbox flags. |
| D97 | **The sandbox works on Windows: a Job Object replaces the refusal.** Every process is put into a Job Object with memory, CPU-time and process limits and kill-on-close, started with its own small environment. A watchdog also enforces a total output size and entry count on every system. | 2026-11-03 | *Reverses the refusal in D90/D96.* **Written from the documentation and never run on Windows**; the first real run is the Windows CI job. A small gap exists between starting the process and putting it into the job. macOS has no address-space limit. |
| D98 | **Installing LaTeX is the user's job; Claudia is told where it is.** `Typesetter(xelatex=…, pdftocairo=…)` take a full path, a folder or a PATH name; symlinks are not followed; the working folder is never searched. Resolution is lazy: a server without LaTeX starts and the first job says what is missing. `Typesetter.diagnose()` checks everything and gives a hint. **Nothing is bundled.** | 2026-11-03 | Replaces the bundling plan for Windows and macOS. `pdftocairo` belongs to poppler, a separate install there. The server option and settings screen are not wired. |
| D99 | **The help entry for this is a topic shipped inside the package** (`claudia_typeset/help/configure-latex.md`), written as a "how do I" topic with numbered steps and a worked example; every message that says LaTeX is missing names its id. | 2026-11-03 | The file is Markdown with simple front matter; **a draft shape** until the real topic format is decided with E13.1. |

## Document container and encryption (seventeenth round)

Renumbered from the E2 design document's D70–D82 (see the table at the top). Details:
`notes/e2-container-and-encryption.md`.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D100 | **Threat model.** Epic 2 defends against (a) an outsider who holds the file and (b) co-editors, who must see only what their role allows. The server operator sees plaintext while a document is open; that is accepted. | 2026-11-02 | Confirms D34. Full text in the notes. |
| D101 | **Key hierarchy.** One slot per user (name and password). A slot wraps the domain keys (content, history, chat) that the user's role may have. Viewers get the content key only. Removing a user deletes the slot; an owner may also rotate keys. The UI says plainly that this cannot recall copies already made. | 2026-11-02 | Refines D20, D34, D35. Key rotation is not built. |
| D102 | **User names are not visible to anyone who is not part of the document's user base.** | 2026-11-02 | The slot is found by a locator derived from name *and* password, so a wrong name and a wrong password are the same answer, and an attacker must guess both together. |
| D103 | **Readable without a password:** document id, title, app type, last change, size, unlisted flag, format version, KDF parameters. This is what the server's document list shows. Server access secret for list and create; creation otherwise only from loopback; unlisted flag as proposed under D53. | 2026-11-02 | Settles the open details of D53. The title is readable by anyone holding the file; the owner chooses it knowing that. |
| D104 | **Primitives:** Argon2id (password to key), HKDF-SHA256 (one secret to several keys) and AES-256-GCM (encryption), from the Python `cryptography` package; the file records the algorithm ids so they can be replaced. No home-made constructions. | 2026-11-02 | Argon2id first appears in `cryptography` 44, so the floor is `>=44`; a `>=43` floor is still declared somewhere and allows an install that cannot open a document (CODE-07). |
| D105 | **Recovery key.** Optional, generated at creation, shown once; 256 random bits, formatted as 13 groups of 4 base32 characters. It opens an owner slot. | 2026-11-02 | Anyone who holds it can read the document; the dialog says so. |
| D106 | **Write path.** An open document is the container zip plus a journal file next to it. When the document is idle or closed the server packs the journal into compressed, encrypted blocks and replaces the zip atomically. An edit is acknowledged only when it is safely on disk. **Every file a person takes away is one complete file.** | 2026-11-02 | The acknowledge-after-fsync part is built; the **group commit off the event loop is not** (PERF-02). |
| D107 | **New package `claudia-container`** (format and crypto, no network code). The kernel stays pure. Plain `--dir` folders from before are not migrated; `--plain-dir` keeps the old store. | 2026-11-02 | |
| D108 | **Unencrypted export and import.** Every user may export the content; only owners may include history and chat. Every unencrypted export is logged: who, when, which parts. The export contains no key slots and no password hashes. Importing creates a new document whose importer becomes owner. | 2026-11-02 | Story E2.9. The log cannot catch copying from the screen; the UI says so. Not built. |
| D109 | **Password rules.** At least 8 characters, containing capital letters, small letters and digits, checked at creation and at every change. Argon2id cost set so one login takes about half a second on the reference machine; the cost is stored in the manifest so it can be raised; a server-wide cap limits how many hashes run at once. | 2026-11-02 | Claude's standing note: against an attacker holding the file, length matters more than composition, and 8 characters is the weak point. **Open:** the measured default is about 0.09–0.4 s, not 0.5 s; a `calibrate(target_seconds)` was proposed and not decided. |
| D110 | **Encrypted Claudia downloads.** Owners get the full file. Editors and viewers get a file with only their own slot and only the parts their keys open. It opens as a standalone copy, not as the live document. | 2026-11-02 | Keeps other users' slots away from offline attacks. Not built. |
| D111 | **Viewers see the names of all users** (the list sits under the content key). | 2026-11-02 | Presence shows them anyway, and a viewer belongs to the user base (D102). |
| D112 | **File extension `.claudia`** for all three apps; the app type is in the manifest. | 2026-11-02 | |

## Native clients (eighteenth round)

Renumbered from the Linux client notes' D97–D103 (see the table at the top). Details: `notes/e5-linux-client.md`.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D113 | **Layout of the native clients:** `clients/<os>/` holds one package per operating system; an app is an entry point, an identity, a menu manifest and its own desktop files under `clients/<os>/apps/<app>/`. The shell contract is shared and lives in `clients/contract/`. The Linux application id of composes is `de.claudiaoffice.composes`. | 2026-11-03 | `clients/contract/` is Claude's addition, because the contract belongs to no single OS. |
| D114 | **The shell contract is a versioned JSON schema.** Additive changes keep the version; anything else is a new version with a new file, and the old file stays while a shell or the web app still speaks it. The page names the highest version it speaks in `hello`; the shell answers with the highest both speak. Unknown message types are ignored; messages are at most 64 KiB. | 2026-11-03 | Answers the versioning part of the open question on E5.12. |
| D115 | **The Linux shell shows a local server on the loopback address, which serves the frontend itself** (`--host 127.0.0.1 --no-tls --web <frontend>` on a free port), so page and WebSocket share one origin and no `--allow-origin` is needed. | 2026-11-03 | Replaces the custom-scheme plan, which cannot work with the unchanged web app because `OpenDialog.vue` derives the server address from `location.host`. Plain HTTP is acceptable because the socket never leaves the machine. **Side effect:** the port changes every start, so the page's `localStorage` does not survive a restart. |
| D116 | **The shell runs on the distribution's Python (3.12 or newer, never forced), the server on 3.14.** The shell is outside the uv workspace and has its own ruff and mypy targets. | 2026-11-03 | Consequence: `claudia-client` needs 3.14 and cannot be imported by the shell, so TLS trust for remote servers is not available to it yet. |
| D117 | **The web app is not changed for the shells (yet); a page adapter speaks the contract for it.** The shell injects `shim.js` into its own pages, carries out actions by using the web app's menus as a person would, reads which items are enabled or ticked, and hides the web menu bar. When the web app implements the contract itself, the adapter is deleted. | 2026-11-03 | The owner asked that the web app not be changed: "that is a separate cleanup". A drift-guard test fails when a web label a route uses is renamed. **Cost:** a DOM click path is fragile, and states are polled every 750 ms (UX-09). |
| D118 | **Rules of the web view in every shell:** the page cannot leave the server's origin; links go to the default browser for web and mail addresses only; permission requests are denied; a downloaded file is saved in Downloads under a name the page cannot use to escape, and never overwrites. | 2026-11-03 | Stop-gap for downloads until a native Save As exists. |
| D119 | **The server never outlives its shell.** It has its own process group, which the shell ends with the window, and it asks Linux for `SIGTERM` when the shell dies for any reason. | 2026-11-03 | Linux only; Windows and macOS need their own mechanism (job object, lifeline). |

## Menu redesign and accessibility baseline (nineteenth round)

Screens only so far (`notes/mockups/`, `notes/e5-1-e5-10-menus-and-accessibility.md`); nothing below is built. Scope
agreed with the owner 2026-11-05, before the screens themselves were reviewed.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D120 | **The menu schema is fixed at seven header-bar menus, identical in every app and every shell: File, Edit, Format, View, Tools, Config, Help.** Edit and View each carry a shared block ahead of an app-specific section (Edit: Undo, Redo, then Copy/Cut/Paste/Paste as ▸ Plain text, then app items; View: Show who did what, History and chat, Dark mode/light mode, then app items). Tools is entirely app-specific. Config is new, holding only Shortcuts for now. | 2026-11-05 | Supersedes D4's four; resolves UX-06. File ships as a flat list with no separators — open item below. |
| D121 | **Scope of the E5.1/E5.10 pass:** the Linux GTK manifest (`manifest.py`) is rebuilt to the full seven-menu schema rather than staying collapsed to D4's four, and is extended to computes and creates, which have no GTK manifest at all today. `shim.js` is retired in the same pass — the web app will speak the shell contract directly, reaching D117's own stated exit condition rather than deferring it further. UX-03 (`Modal.vue` → native `<dialog>` + `showModal()`) ships alongside UX-01/04/05 instead of being sequenced after. | 2026-11-05 | Supersedes the "not changed for the shells (yet)" half of D117; D117's versioned-contract mechanism itself stands. |
| D122 | **Keyboard shortcuts move to one shared, structured map**, replacing the three near-identical hardcoded `keydown` handlers in `TextWorkspace.vue`, `DocumentFrame.vue` and `Workspace.vue`, with GNOMEish defaults — e.g. Redo is Ctrl+Shift+Z only, dropping today's extra Ctrl+Y binding. Config ▸ Shortcuts shows this read-only for now; an editable remapping UI is deferred. | 2026-11-05 | Groundwork for shipping "typical" per-OS shortcut sets later, per the owner. |
| D123 | **Where today's items land in the new schema:** insert-like items (creates' text box and shapes, computes' row/column insert-delete and Clear cells) and the "New sheet…" / "New slide" actions move to Edit's app-specific section, not File or Tools. File ▸ Download ships as a stub — today's single-format Save-As action, relabelled — until real export formats exist. File ▸ "Save new checkpoint" is today's "Save with a name…", renamed. "Close document" keeps its current meaning (back to the document list, not quit). | 2026-11-05 | Confirmed directly by the owner. |

The owner's first look at the screens (same day) settled most of what D120 had left open:

| ID | Decision | Date | Notes |
|---|---|---|---|
| D124 | **File keeps separators**, grouped New, Open \| Save, Save new checkpoint, Download \| Share \| Close document. | 2026-11-05 | Supersedes D120's flat-list reading. Claude's grouping, from the pre-redesign pattern — not individually confirmed item by item. |
| D125 | **A menu item with nothing behind it yet stays visible but inert, rather than being hidden:** computes' and creates' empty Format menu (no style system yet), and Help's "How do I…?" and "Documentation" (no help system yet, E13). | 2026-11-05 | Confirmed by the owner, one pattern for both cases. |
| D126 | **Help ▸ "Ask ai" is a generic "open chat, empty prompt" entry point**, distinct from Tools' task-specific AI actions (Review this text, Ask for an example budget, …). Today's Help ▸ Keyboard dialog content moves into Config ▸ Shortcuts instead of staying under Help. | 2026-11-05 | Confirmed by the owner. |
| D127 | **composes' Format menu groups its style names**, rather than the flat list D120 carried over from the original sketch. | 2026-11-05 | Grouping shown in `notes/mockups/menu-bar-states.svg` (separators by style family) is Claude's proposed reading of "grouped" and has not yet been checked against the owner's actual style set. |
| D128 | **A dialog always closes on Esc, including a "locked" one** (e.g. Save new checkpoint) — only an outside click is still blocked for a locked dialog. Esc stays a deliberate, always-honoured exit; the outside-click guard is what protects against an accidental dismiss. | 2026-11-05 | Supersedes the Esc-blocked-when-locked reading in the first round of UX-03 screens. |
| D129 | **UX-04's contrast fix and the UX-05 dark-mode token proposal are agreed as shown** in `notes/mockups/contrast-and-dark-mode.svg`. `tokens.css` can be changed. | 2026-11-05 | The white-text-on-`--app` 3.9:1 note stays open (see below) — agreeing the sheet did not resolve that part. |

The owner then asked whether computes' Edit menu, grown long with row/column actions, should group them:

| ID | Decision | Date | Notes |
|---|---|---|---|
| D130 | **computes' Edit menu groups its row and column actions into two submenus — "Row ▸" (Insert above, Insert below, Delete) and "Column ▸" (Insert left, Insert right, Delete)** — instead of six flat items, reusing the submenu mechanism already built for "Paste as ▸ Plain text" rather than adding a second one. | 2026-11-05 | Claude's recommendation, given in answer to the owner's question; not yet confirmed. Shown in `notes/mockups/menu-bar-states.svg`, panel C. |

The owner ran the applied patch in dark mode a second time and reported a further, larger round of contrast and
boundary bugs. Asked for design suggestions before any code; two choices were put to the owner and answered:

| ID | Decision | Date | Notes |
|---|---|---|---|
| D131 | **Native shell chrome (the GTK/libadwaita About dialog) follows the page's own Dark Mode toggle, not the desktop's theme.** The window already reports `view.dark`'s resolved `checked` state to the shell on every change (click or system-triggered); the shell now also feeds that into `Adw.StyleManager.set_color_scheme()`, forced light or dark to match — never `PREFER_*`, since the in-app toggle is meant to override the desktop setting, not just suggest to it. | 2026-11-06 | Owner's report: the About dialog stayed whatever colour GTK's own theme was, regardless of the document's own Dark Mode setting. Chosen (over leaving native chrome theme-independent) via `AskUserQuestion`. No new shell-contract message needed — `set_action_states` already received everything required. |
| D132 | **A document's own default ink (stored as black, however written) is swapped for the page's own text colour at display time only, never in the stored style.** Applies wherever a style's computed CSS reaches the page — composes' paragraphs and creates' text/shape objects alike. | 2026-11-06 | Owner's framing: "in the document they would count as black obviously" — typed text was unreadable, black-on-near-black, in dark mode because a style's stored `color` always overrides the container's theme-aware default. Chosen (over a document-wide black→ink-token migration, which would have changed stored data) via `AskUserQuestion`. Web client only, per the owner's choice; GTK has no document rendering of its own to fix. |

## Quality gate truthfulness (twentieth round)

QA review of code quality and technical debt (PROC-02, PROC-03, DOC-01, CODE-07, CODE-08). Three of the project's own
quality signals — the gate, a note, the decision log's own numbering — turned out to say things that were not true,
each found by accident rather than by a check that was looking for it.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D133 | **The gate never reports "clean" over a skipped check**, and a `--ci` flag turns an unlisted skip into a failure. `check_debt.py`'s `verdict()` prints `clean except skipped: …` whenever anything skipped, even under `--ci` with the skip allow-listed — an allowed skip still must be named, never folded silently into "clean." CI now calls `check_debt.py --ci`, explicitly allow-listing the three checks the Python job's own OS/toolchain cannot run (`web tests`, `web types`, `linux client tests`), which the separate `web` and `linux-client` jobs cover for real. `ruff format --check .` joins the gate as its own named check (CODE-08). Three new repo-scanning tests close the rest: every `D<number>` cited in source resolves to exactly one row in this log (DOC-01); no `.rej` or `.orig` file is ever tracked (CODE-07); and a note under `claudiaoffice-log/` may say "built" about a path only if that path is actually in the tree (PROC-03) — the guard `e4-e6-formulas-notes.md`'s own false claim should have tripped. | 2026-11-06 | Fixes PROC-02 (the gate's false "clean"), DOC-01 (D70–D82/D97–D99 each allocated twice across `claudia-container`/`claudia-server`, resolved by this log's D100–D119 renumbering — citations in source updated to match), CODE-07 (`uv.lock.rej` deleted, lock regenerated, `cryptography` floor corrected `>=43`→`>=44`), CODE-08 (`ruff format --check .` added to the gate). PROC-03's underlying feature (point-and-click cell references, E6.3) was already rebuilt and committed by the owner before this review; this round added only the guard and the note correction. |

## Worker pool placement (twenty-first round)

QA (PERF-01/02/05) found `Connection.handle` running every request on the event loop: two O(sheet-size) hot paths
(the `_cells` grid-window query and the sheets' `_extent`) and `_cells.py`'s synchronous `os.fsync` each stall every
document the process holds. The fsync fix and the O(sheet-size) fix are both below; this round is about the worker
pool that D37 already specified for the fsync tier (and that E4.3/E4.4/E4.9/E3.4 are blocked on) but that was never
built. Raised by the owner: "where should we locate the worker pool and multi processing? I think it best to have it
in the core, so it can be re-used in any of the three apps." Discussed and agreed before building.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D134 | **The worker-pool abstraction (a generic `submit(fn, *args, **kwargs)` over a `ProcessPoolExecutor`, bridged into `asyncio`, with crash isolation if a worker process dies outright) lives in `claudia-server`, not `claudia-core`, and each server process owns exactly one instance of it, started and stopped with its `Hub`.** | 2026-11-06 | Owner's opening framing ("in the core, so it can be re-used in any of the three apps") turned out to rest on a wrong premise, corrected while reading `cli.py`: `make_plan()` starts exactly one `Hub` per OS process, for exactly one `--model` (one app type). There is no single running `claudia-server` process that already hosts composes, computes and creates together — the real topology is one process per app type. So reuse across apps was never going to come from a shared running instance anyway; it comes from the abstraction being available to every process that is a `claudia-server` process, which all three already are. `claudia-core` stays dependency-free and I/O-free (`pyproject.toml: dependencies = []`) — `asyncio`, `ProcessPoolExecutor` and process lifecycle do not belong in the pure kernel. Each process owning its own pool (over one pool shared across processes) was agreed directly: a document-hosting process must be able to start, stop and recover its pool without coordinating with any other process. Built in `packages/claudia-server/src/claudia_server/workers.py` (`WorkerPool`, `DEFAULT_WORKERS`), wired as `Hub.workers`. |

Separately, the O(sheet-size) cost itself (PERF-01/05) was fixed without a worker pool: `_cells`/`_extent` moved from a
full scan to an index (sparse row→sorted-columns map, plus lazy-deletion max-heaps for the row/column extent)
maintained incrementally at `WorkbookModel.store()`'s single per-cell mutation point, falling back to the existing
O(sheet-size) rebuild only for structural edits and document load. An invalidate-and-rebuild cache was considered and
rejected: the measured workload interleaves edits and window queries closely enough (a user scrolling while another
edits) that a rebuild-on-next-read would frequently pay the full O(sheet-size) cost anyway, with none of the
incremental approach's guarantee that cost tracks the window, not the sheet.

## Row height and column width (twenty-second round)

| ID | Decision | Date | Notes |
|---|---|---|---|
| D135 | **Row heights and column widths are sheet layout, not a cell style** — resolves E6.13's open point ("whether row heights and column widths are style or sheet layout; proposal: layout"). Stored as sparse per-line overrides on the sheet (`Sheet.row_heights`/`col_widths`, pixels; a line not listed shows at the default, `DEFAULT_ROW_HEIGHT`/`DEFAULT_COL_WIDTH` = 26×96, matching the grid's current fixed size), set and undone through a new `computes.ResizeLines` command exactly like a structural edit — remapped by row/column insert and delete, restored when `Structure` or `RemoveSheet` is undone, conflict-checked against a colleague's own resize of the same line via `shifted_by()` — and independent of the not-yet-built CSS style system (E6.13), which governs cell/range/row/column appearance, not line size. Server: `sizes` (read) and `resize_lines` (write) methods, the latter on the AI's method allow-list alongside `set_cells`/`add_sheet`/`structure`. Patch 1 of two (model/command/server, fully tested); the web grid's variable-height rendering, drag-resize and the context-menu dialog are Patch 2, not yet built. | 2026-11-06 | Chosen (over folding sizes into the E6.13 style system) via `AskUserQuestion`; the owner had no preference on including extras or on recording a decision, so both were the author's own call, flagged as such. Fixes two latent gaps the new state exposed: `RemoveSheet.apply()` and `Structure.apply()` previously restored cell content on undo but not row/col sizes, silently losing custom sizes on remove/delete-then-undo — fixed as part of this patch since the codebase's undo contract requires an exact inverse. |
## The Manage menu: leaving, handing over ownership, exporting and deleting (twenty-first round)

Stories E2.3 (leave or remove a collaborator) and E2.9 (export). Built in full — not a mockup — for all three apps, on
the server, the web client and the Linux shell, from a fresh `main` checkout, as a patch for the owner to apply.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D135 | **File ▸ Manage replaces the flat Share item with a submenu of six:** Share…, Assign new owner…, Accept ownership…, Leave document…, Export…, Delete from server…. Built for composes, computes and creates alike, on the web and in the GTK shell manifest, under the shared id namespace `file.manage.*`. | 2026-11-06 | "Accept ownership…" was not in the original mockup — added because the propose/accept transfer flow (D136) is otherwise unreachable by the person being handed the document. This round also re-fixed `uv.lock.rej`'s staged deletion (D133 deleted the file on disk but never staged the `git rm`) and closed DOC-01 for this round's own new citations. |
| D136 | **Handing over ownership is a two-password handshake, not a single action.** The current owner proposes with their own password and the new owner's name; the new owner must already be an editor; the new owner then accepts with their own password, inside a time window. | 2026-11-06 | A person's role is baked inside their own password-sealed slot (D101); changing it means re-deriving the sealing key from that person's *current* password, which only that person's own password can do. This is also why a role change could not previously be done without remove-and-re-add. |
| D137 | **A proposed transfer lives only in server memory, for five minutes by default, and is used at most once** — popped on the first accept attempt whether it succeeds or fails. | 2026-11-06 | Keeping the old owner's plaintext password briefly in memory is a deliberate, precedented tradeoff: `sealed.py` already holds raw domain keys in memory the same way between login and open. |
| D138 | **Leaving a document is a new primitive, separate from removing someone else.** `leave_document()` needs none of the three domain keys — a viewer holding only the content key can still remove their own slot — while `remove_user()` still requires all three. The only invariant anywhere is "at least one owner remains," never "exactly one": `add_user(..., Role.OWNER)` already adds a second owner with no special ceremony. | 2026-11-06 | Corrects an earlier working assumption that the container only ever allowed a single owner; it does not, and nothing new had to be built to allow a second one — only to let someone leave without holding every key. |
| D139 | **Export ships content-only for now**, matching D108's split: history, chat, and any Word/Excel/PowerPoint import or export stay out of scope. The dialog says plainly that this is Claudia's own file format, not another office format. | 2026-11-06 | Leaves the rest of E2.9 (history/chat export, other-format import/export) open. |
| D140 | **`ruff` is pinned to `>=0.6,<0.15`.** Every release from 0.15.0 through 0.17.4 (the latest published) reformats a valid `except (A, B):` into the invalid `except A, B:` — confirmed by bisection, and by `ast.parse` raising a real `SyntaxError` on the result. `uv.lock` had already resolved the regressed version this round surfaced it under; this is how CODE-08's `ruff format .` broke 10 files (see CODE-10) at commit `558f429`, the very commit that added the `ruff format --check` gate it then silently failed. | 2026-11-06 | Fixes CODE-10. No upstream fix exists at review time; the pin is removed once one does. |
## Additive xlsx/docx/pptx extensions (twenty-second round)

Closing a separate gap found while looking at import/export: each app's own format library writes a correct base
file but cannot write everything the app's model can hold (a pivot table, a tracked change, a slide transition).

| ID | Decision | Date | Notes |
|---|---|---|---|
| D135 | **Microsoft-format gaps that openpyxl/python-docx/python-pptx cannot write (xlsx pivot tables, docx tracked changes, pptx transitions) are closed by editing the library's own already-written zip/element tree with `lxml`, never by forking the library.** Validated first as three standalone spikes (structurally consistent, read correctly by LibreOffice, and surviving a load-edit-save round trip through the library's own code), then built as three new workspace packages — `claudia-computes-io`, `claudia-composes-io`, `claudia-creates-io` — each depending on `claudia-core`, its one app package and its one format library (`openpyxl`, `python-docx`, `python-pptx`, as `>=` floors, matching the repo's existing pin style, not exact pins). Each package pairs a minimal base export from the app's own model (`workbook_to_xlsx`, `text_to_docx`, `slides_to_pptx`) with the one additive extension the spike covers (`add_pivot_table`, tracked changes folded into `text_to_docx` from `TextModel`'s own open suggestions, `add_transition`); `text_to_docx` is the one place a suggestion's `original`/`replacement` becomes real Word markup instead of being silently dropped. None of the three is in `scripts/api_surface.py`'s frozen `PACKAGES` list yet (same "first slice" status as `claudia_computes`/`claudia_composes`). | 2026-11-06 | Resolves the brainstorm on import/export architecture: researched library gaps (not "openpyxl has no cell styling," which was a wrong premise, but real gaps in pivot-table write support, track changes and transitions), ruled out forking or a shared `python-xlsx` (no thin OOXML layer exists to extract; xlsx's own gaps are business-logic, not packaging), chose "extend additively" over the alternative of putting the format libraries inside `claudia-core` (refused by the kernel's own purity tests — `claudia-core` does no I/O and knows no format) via `AskUserQuestion`. `odfdo` is deliberately **not** a dependency of any of the three packages yet: D70 (see also D5, D67, D69) wants ods/odt/odp import and export before xlsx/docx/pptx in every app, and nothing here is that story — adding the dependency without a spiked ODF gap to extend would be dead weight. The full ODF-first, loss-reporting import/export of E6.9/E9.5/E10.3 remains open. |

## Open design questions

- **Typesetting:** the full-document comparison of E0.4 (Tectonic against TeX Live, biblatex with biber, Beamer,
  offline), a curated and pinned package set, and whether the live preview of a formula needs a faster engine than the
  final output.
- **Bibliography and LaTeX (D86–D88), none decided:** BibTeX entry types and fields and how text is stored; the
  citation style engine (CSL or biblatex through the engine), where the same style must give the same list in the
  browser and in the export; where a reference-manager connector runs and where its credentials live; whether the page
  view is typeset by the engine (server-side layout) or by the browser; the LaTeX import subset; the Beamer theme.
- **Help system (D76), none decided:** the topic file format, the search service, whether an extension without help is
  refused in composes and creates too, where the help view lives, and whether tooltips could default from docstrings.
  **And now also:** Help's "How do I…?" and "Documentation" ship as visible, inert stubs until this exists, and
  today's Help ▸ Keyboard dialog content moves into Config ▸ Shortcuts instead of staying in Help (D125, D126).
- **Shells:** Neutralino on Windows and macOS against GTK on Linux — window behaviour, menus, dialogs, input methods,
  accessibility, install size, maturity (E0.3, E0.8). Nothing is verified.
- **Menus:** four or six (UX-06) is resolved — D120, seven, identical everywhere; GTK extended to all three apps and
  `shim.js` retired — D121; File's separators (D124), the empty-but-visible treatment (D125), Help's "Ask ai" (D126)
  and style grouping (D127) are all settled. Still open: Select All (never decided for any menu); Tools as entirely
  app-specific (D120) is a working default the owner has not revisited ("don't know yet, not too much for it at the
  moment") — nothing blocks on it, since Tools already has real content in every app today; computes' Edit ▸ Row ▸ /
  Column ▸ grouping (D130) is proposed, not yet confirmed.
- **Styling:** deleting a style that other styles are based on (a proposal exists: deleting never changes how anything
  looks and never leaves a dangling reference; the person chooses "keep their look" or "re-base on another style"; root
  and built-in styles cannot be deleted, only hidden); where the dialog appears, with a mock-up (a popover at the caret
  is built and a review is still wanted). Row heights and column widths are settled as sheet layout, not style (D135).
- **Numbers:** the INT type and numeric semantics (E6.4). What is built: whole numbers exact to 2^53 then float, `/`
  always float, no coercion of text, TRUE/FALSE as 1/0, `math.fsum` for sums. Not yet confirmed as a decision.
- **KDF cost calibration (D109):** keep the defaults or calibrate per machine at creation, with a floor. The measured
  default is below the target, and OpenSSL's multi-lane Argon2id serialisation makes it a throughput question too.
- **The redaction contract:** what a command's `redacted()` must keep so later commands still replay, and what happens
  when the redacted log no longer replays. Affects E1.8 and E2.6, and now also the container (SEC-05).
- **The AI's authorisation boundary:** whether the method allow-list moves from the model's output parser to the
  server's dispatch, before E7.5 puts document content in the prompt and before D8 makes the engine remote (SEC-10).
- **Where the AI's permissions come from:** the intersection of the AI's role and the asker's (E7.4); fairness,
  cancellation and queue visibility in the AI server; structured output for small local models.
- **Which use case comes first** (PM, FIN, SCI, DATA, EDU).
- **Accessibility standard** to aim at, and which countries' administrations to interview first.
- **White text on the base `--app` colour (e.g. Teal) as a filled background measures 3.9:1** — under the 4.5:1
  normal-text bar, though it clears 3:1 for UI components/large text. Not one of UX-04's five measured pairs, and
  agreeing D129 did not resolve it — noticed while building the dark-mode screen; worth a look independently of
  dark mode. Dark-mode tokens themselves are agreed (D129).
- **Side effects of D51/D52 to settle elsewhere:** redaction has to reach hidden lines, or a secret removed from the
  active line stays in the file; viewers must not see hidden lines; chat is not rolled back by a restore; after a
  restore the `ai` user must rebuild its context.
- Branching what-ifs and scrubbing back in time: revision ids allow branches, but there is no API for free what-if
  branches, only the restore fork.
- How old a bundled frontend the server must keep supporting (D43).
- Font licences: the licence of the Latin Modern and TeX Gyre fonts (believed GUST Font License) is not verified.
- Macro API for composes and creates. Name check for "Claudia" (trademark, existing products).
