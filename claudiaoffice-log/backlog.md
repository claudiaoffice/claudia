---

kanban-plugin: board

---

## todo

- [ ] **E0.5 · Runtime fonts spike**
	As a developer, I want to register a downloaded font at runtime in the GTK client on all three OSes and in the browser, so that "the server provides missing fonts" (D26) is feasible.
	
	AC: a font fetched from the server is used in a GTK label on each OS without admin rights and is gone after exit; the same paragraph is laid out in GTK/Pango and in a browser and the difference in line breaks is measured and written down.
	
	Use case: ALL · Decisions: D26, D42 · With the web frontend (D42) all document text is web and fonts load by `@font-face`, so this may shrink to the browser half. Composes needs the result for E9.4.
	
	Status evidence: nothing in the tree.
- [ ] **E0.6 · Installer skeleton**
	As a developer, I want a CI job that produces an installable artifact for Linux, Windows and macOS, so that packaging is never a late surprise.
	
	AC: CI builds and installs the prototype on clean machines of each OS; signing and notarization needs (accounts, certificates, cost) are listed.
	
	Use case: PLATFORM · Decisions: D16, D22, D42 · Windows and macOS packages hold the Neutralino shell, the bundled frontend and the server bundle, no GTK. On Linux the natural form may be Flatpak, where the platform supplies GTK; D16's "interpreter always bundled" then needs a decision.
	
	Status evidence: `.github/workflows/ci.yml` runs tests only; no packaging job.
- [ ] **E2.6 · Redaction in the container**
	As an owner, I want redaction to rewrite the affected blocks and purge caches, so that content is really gone from the file.
	
	AC: block rewritten; snapshot cache rebuilt; unreferenced assets removed; a test shows the redacted bytes are absent from the file; hidden side lines are covered.
	
	Use case: ALL · Decisions: D21, D34 · Tracked as SEC-05 in `bugtracker.md`, which is the reason this is no longer only a backlog item.
	
	Status evidence: `claudia_container.container` has no `redact`; the journal is append-only and packing does not rewrite history. The kernel redacts the live state; the bytes stay in the file.
- [ ] **E2.9 · Unencrypted export and import**
	As a user, I want to export a document unencrypted and import such a file, so that I can leave the product, archive in an open format, and hand over a readable copy.
	
	AC: File ▸ Save As offers "Claudia, unencrypted (JSON in a zip)", producing **one** documented file; every user may export the content, only owners may include history and chat (hidden side lines included); every unencrypted export writes a log record (who, when, which parts), written by the server on a viewer's behalf; the export contains no key slots and no password hashes; importing creates a new document whose importer becomes owner and sets the passwords, and replaying the imported log gives the identical state; help text says the log cannot detect copying from the screen.

	Use case: ALL · Decisions: D108, D19, D34, D145 · Whether the record is a new kernel entry or a record in the history domain is decided while building.

	Status evidence: content-only export is built — File ▸ Manage ▸ Export… (every role may use it) produces one documented JSON file with no key slots and no password hashes, for all three apps, web and GTK. **Not done:** owners-only history and chat export; the unencrypted-export log record; import; the help text on screen-copying. The export dialog says plainly that this is Claudia's own file format, not Word, Excel or PowerPoint — that conversion is separate, future work.
- [ ] **E2.10 · Delete a document from the server**
	As an owner, I want to remove a document from the server entirely, so that a document nobody wants kept any more does not just sit there.

	AC: only an owner may delete; the document's file and any server-side bookkeeping about it are gone; everyone who had it open is told at once and returned to their document list; deletion cannot be undone and the confirmation says so.

	Use case: ALL · Decisions: D141 · Built directly as a `DeletableDirectory` capability of `SealedDocuments`, alongside leave and transfer-ownership, rather than as its own story up front.

	Status evidence: built — `delete_document` on the server, `file.manage.delete` in the Manage menu (web and GTK), an `ephemeral` `document_deleted` push that closes every other open connection to it. **Not done:** nothing server-side; the lightweight demo backends (`ScryptDirectory`/`FileDirectory`) do not implement it, matching how they already skip `RecoverableDirectory`.
	
	Use case: ALL · Decisions: D108, D19, D34 · Whether the record is a new kernel entry or a record in the history domain is decided while building.
	
	Status evidence: nothing in the tree.
- [ ] **E3.2 · Protocol schema as one source**
	As a client developer, I want TypeScript and Python types generated from the protocol table, so that GTK and web clients cannot drift.
	
	AC: the `/api/protocol` schema drives generated types; hand ports are replaced or tested against the Python reference.
	
	Use case: PLATFORM · Decisions: D2 · `/api/protocol` exists and describes methods, parameters, error codes and events; the generator does not. `web/app/lib/protocol.ts` is still hand-written.
- [ ] **E3.5 · Worker pool service**
	As a calculation developer, I want a shared pool of warm worker processes with timeouts and cancellation, so that slow code never blocks a document.
	
	AC: submit, cancel, timeout, crash containment; inputs by shared memory; bundle-compatible (E0.2); metrics.
	
	Use case: PLATFORM · Decisions: D37 · The E0.2 spike proposes the lifetime protocol: lifeline pipe from shell to server, parent-sentinel watchdog in every worker, tree kill on timeout, kill-busy-first on shutdown. Tested on Linux only.
	
	Status evidence: no `multiprocessing`, process pool or forkserver anywhere under `packages/*/src`. This is the root cause behind PERF-01, PERF-02 and PERF-05: everything runs on the one event loop.
- [ ] **E4.3 · Calculating state and stale results**
	As a user, I want a cell with a slow result to show its old value dimmed and "calculating…", so that I know what is current.
	
	AC: results carry the revision of their inputs; stale results are discarded; the state shows in every client; `#TIMEOUT` for killed jobs.
	
	Use case: ALL · Decisions: D37 · Needs E3.5. Today every calculation is synchronous, so there is no state to show — which is itself the problem.
- [ ] **E4.4 · Heavy functions in workers**
	As a function author, I want slow functions to run in worker processes, so that they do not block other users.
	
	AC: functions declared heavy, or measured slow, run in workers; calls batched per dependency layer; timeout, cancel and crash containment demonstrated.
	
	Use case: SCI, DATA · Decisions: D37, D38 · Needs E3.5.
- [ ] **E4.5 · Worker results in the log**
	As an owner, I want results of worker functions recorded in the history, so that replay and time travel never re-run a job.
	
	AC: a result command with final values, function name, version and digest; large results as content-addressed blobs; superseded results may be compacted; a new digest marks old results stale and triggers recomputation.
	
	Use case: SCI, DATA · Decisions: D15, D37
- [ ] **E4.8 · What-if preview**
	As a user, I want dragging a value to show the effect immediately without filling the history, so that I can explore.
	
	AC: preview evaluation on a throwaway overlay; only the committed value becomes a command; requests coalesce (latest wins); other users see the preview as presence, not as edits.
	
	Use case: EDU, SCI, FIN · Decisions: D33, D37 · One of the Bret Victor features of D33 and a precondition for E6.10 and E13.7. Nothing of it exists.
- [ ] **E4.9 · SQL cells on the new engine**
	As an analyst, I want `SELECT` over named ranges to keep working, so that the demo's feature survives.
	
	AC: ported with the demo's rules (read-only, one statement, size limits); runs in workers; incremental dependencies; `#SQL!`/`#SPILL!` behaviour kept.
	
	Use case: DATA · Decisions: D18, D37 · One of the two signature features of the demo named in D18. Needs E3.5 and E6.5.
- [ ] **E4.10 · Function hot reload and New Function**
	As a local user, I want to create and edit a function in a few seconds, so that extending Claudia is easy.
	
	AC: Tools ▸ New Function… creates a template in the profile folder (with a tooltip, a help topic and a tested example to fill in) and opens it; saving reloads the workers; errors show in Tools ▸ Functions; a digest change marks results stale; on a network server the same folder is admin-only.
	
	Use case: ALL · Decisions: D29, D38 · The other signature feature of D18.
- [ ] **E4.12 · Large tables**
	As an analyst, I want to import a million-row table without a million cell objects, so that data analysis is practical.
	
	AC: a table object backed by a column store (content-addressed blob in the container); cells in its region are views; sort, filter and SQL work on it; the log records a hash, not the data.
	
	Use case: DATA · Decisions: D16, D33 · Needs a design discussion before it is `ready`.
- [ ] **E5.7 · Internationalization**
	As a translator, I want every text to come from translation catalogs, so that Claudia can be translated.
	
	AC: gettext `.po` as the single source, read by both GTK and web; extraction in CI; English complete; a test language proves nothing is hard-coded; numbers and dates typed by a user are parsed with that user's locale before a command is made.
	
	Use case: ALL · Decisions: D31 · D31 says i18n is built in **from the start**; it is the oldest unstarted decision in the log, and the cost of retrofitting grows with every screen. The Linux client marks its labels translatable but no catalogue exists.
	
	Status evidence: groundwork built (D148) — kernel error codes, the protocol's `locale` field, a GTK gettext
	skeleton and a web loader skeleton, `po/claudia.pot` extraction gated in CI, a pseudo-locale proving the
	pipeline. Still open: no real string has moved off plain English into `_()`/`t()` anywhere; no Config-menu
	override (no screen design yet); numbers/dates typed by a user are not locale-parsed before a command is made.
- [ ] **E5.10 · Accessibility baseline**
	As a user with a screen reader or keyboard only, I want to operate Claudia, so that it is usable by everyone.
	
	AC: keyboard reachability of all menus and the history panel; labels for assistive technology; contrast checks; a checklist per release.
	
	Use case: ALL · Decisions: D3, D42 · D69 names public administration and schools, who in the EU usually have to meet WCAG 2.1 AA through EN 301 549 (BITV 2.0 in Germany). Open bugs: UX-01 (menus), UX-02 (grid), UX-03 (dialogs), UX-04 (contrast), UX-05 (dark mode).
- [ ] **E5.11 · claudia-shell-neutralino (Windows, macOS)**
	As an app developer, I want a Neutralino shell for Windows and macOS with the OS title bar and a native menu around the bundled frontend.
	
	AC: configuration with the native API restricted (allow lists, file scopes, one-time token); a native main menu from the manifest including the macOS application menu; native file dialogs; About, theme and scale from the OS; starts and stops the server bundle; installers; a thin adapter so Tauri or pywebview could replace Neutralino.
	
	Use case: PLATFORM · Decisions: D42, D43, D44 · Depends on E0.3. Neutralino 6.8.0 has now run on one Mac and one Windows 11 machine with all automatic checks passing (D156), so the bet is no longer unverified, but it is not yet confirmed either: see E0.3 for what is untested. **Acceptance items learned from the spike:** `tokenSecurity: one-time`, the page loads only `js/neutralino.js` (D157); Edit items with Cocoa `action` and `shortcut` on macOS; printing through `Neutralino.window.print()`; binary and client library versions pinned together; the allow-list shrunk from the spike's wide one; the About dialog stays a page dialog; Windows 10 without a WebView2 runtime handled or refused with a message. **Open before building:** how the real frontend reaches the shell under D115 (D159), which decides the transport the web app needs.
- [ ] **E6.5 · Names and SQL in cells**
	As an analyst, I want named ranges and SQL, so that I can query my sheets.
	
	AC: names follow structure edits; SQL via E4.9.
	
	Use case: DATA · Decisions: D18
	
	Status evidence: no `DefineName` command and no named-range handling in `claudia-computes`.
- [ ] **E6.6 · Charts**
	As an analyst, I want charts that update live and respond to clicks, so that I see my data.
	
	AC: bar and line first, then scatter; rendering per E0.3; the same look in web and desktop; a click-to-edit hook.
	
	Use case: DATA, EDU · Decisions: D33, D42 · Charts are Plotly figures inside the page, the same in every shell. Plotly is the reason the whole web-surface architecture (D41, D42) was chosen, and no chart exists yet.
	
	Status evidence: no plotly, no chart code anywhere.
- [ ] **E6.9 · ods and xlsx import and export**
	As a user, I want to open and save OpenDocument spreadsheets first and Excel files second.
	
	AC: import and Save As .ods (first, on the shared ODF layer of E12.6) and .xlsx for values, formulas, number formats, sheets and basic charts; a list of losses shown on import; the native format stays and is the only one with history and chat.
	
	Use case: ALL · Decisions: D5, D19, D70 · The website promises this today (WEB-01).
- [ ] **E6.10 · Live controls**
	As an explorer, I want sliders and scrubbers bound to input cells, so that I can feel how assumptions move results.
	
	AC: a control bound to a cell; dragging uses the E4.8 preview and commits on release; works for several users at once.
	
	Use case: EDU, SCI, FIN · Decisions: D33 · Bret Victor's immediate connection. Depends on E4.1 (done) and E4.8 (not started).
- [ ] **E6.11 · Showing dependencies**
	As a learner, I want to see which cells feed a result and which depend on it, so that I understand a model.
	
	AC: highlight precedents and dependents of the selected cell; intermediate values shown on demand.
	
	Use case: EDU, FIN · Decisions: D33 · The calculation engine already holds the dependency index this needs, so the server half is nearly free; only the wire method and the drawing are missing.
- [ ] **E6.12 · Project-management and simulation features**
	As a project manager or teacher, I want timeline and simulation helpers, so that Claudia serves those use cases.
	
	AC: to be written after the decision on which use case comes first.
	
	Use case: PM, EDU · Decisions: D33 · Placeholder. Blocked on the open decision "which use case comes first", which is the oldest unanswered product question in the log.
- [ ] **E6.13 · Cell styles with CSS table properties**
	As a user, I want to style cells, ranges, rows and columns with named styles that use CSS table properties.
	
	AC: a cell carries a style name, settable for a cell, range, row, column or sheet default, layered in a fixed order, and the dialog says where a cell's look comes from; properties from the allow-list; style ranges stored as runs or ranges, not per cell, moving with row and column edits, measured with a million styled cells; the grid draws from the computed styles without an element per cell; ODS and xlsx export map the named styles.

	Use case: ALL · Decisions: D73, D75, D17 · Row heights and column widths are sheet layout, not part of this card (D135, E6.16). Depends on E1.10, E6.1, E6.3.
- [ ] **E6.14 · Number and date formats**
	As a user, I want named number and date formats, so that values look right for their purpose and my locale.
	
	AC: a format is a named definition of its own, not CSS; formats follow the person's locale for display while the stored value is independent of it; mapping to ODS and xlsx formats with losses listed; tests for rounding, negative, large and small numbers, and German and English date formats.
	
	Use case: FIN, SCI · Decisions: D75, D31 · Related to the numeric-semantics decision (E6.4).
- [ ] **E6.15 · Typeset text in cells, labels and chart titles**
	As a scientist or teacher, I want a cell, a label or a chart title to show typeset LaTeX.
	
	AC: a cell, text label or chart title can be marked as LaTeX and is rendered by the typesetting service and drawn as an image, with the source staying the cell content that formulas and search see; the `=$$\frac{x}{y}$$` cases work; rendering never blocks the grid; output is cached and shown as an image, never inline.
	
	Use case: SCI, EDU · Decisions: D88, D66 · Depends on E3.4 and E6.3. A sheet with thousands of typeset cells needs batching and limits.
- [ ] **E6.16 · Row height and column width**
	As a user, I want to set a row's height and a column's width, changeable from the header, so that I can make room for what a sheet holds.

	AC: a row/column shows at a sheet default when nothing overrides it; a right-click on a row or column header opens a dialog to set its size in pixels, with range limits enforced; dragging the border between two row or column headers resizes the one above/left of the border live as the mouse moves; one command resizes one or many rows/columns at once and undoes as one step; a size survives row/column insert and delete (remapped to the moved line) and survives removing and restoring a sheet; merged cells are out of scope.

	Use case: ALL · Decisions: D135 · A narrower, already-layout-settled split out of E6.13 (styling), not dependent on it. Depends on E1.10, E6.1, E6.3.

	Status evidence: model, command, undo/redo, serialization and the server's `sizes`/`resize_lines` methods are built and tested (`claudia_computes.model.Sheet.row_heights`/`col_widths`, `claudia_computes.commands.ResizeLines`, `claudia_server.computes._sizes`/`_resize_lines`). The web grid still draws every row/column at the fixed default (`SheetGrid.vue` has no variable sizing yet) and there is no drag-resize or context-menu dialog — those are Patch 2, not started.
- [ ] **E7.2 · skills.md and persona.md**
	As an app author, I want skills and persona files per app, so that the AI behaves right in each.
	
	AC: a loader and a location; files chosen by the app type the doc server announces; examples for the three apps; a test shows each app gets only its files; the files tell the AI to look in the help system before answering questions about how to use Claudia.
	
	Use case: ALL · Decisions: D9, D24 · Decided on day one (D9) and still not started.
- [ ] **E7.4 · AI permissions**
	As an owner, I want the AI to act with the asker's rights, so that it is never a way around a role.
	
	AC: effective rights = the intersection of the AI's role and the asker's; the history shows "ai, on behalf of X"; tested with a viewer. Across two documents it uses a session in each, under the asker's rights in each, and never carries content from a document the asker cannot read into one she can.
	
	Use case: ALL · Decisions: D6, D35, D65 · Related to SEC-10, fixed 2026-11-06: the allow-list now lives in `Account.allowed_methods`, checked at dispatch, rather than in the model's output parser — but the account is still the assistant's own fixed, per-app one. Nothing yet intersects it with the asker's rights, which is what this story still needs.
- [ ] **E7.6 · AI cannot install code**
	As an admin, I want a guarantee that the AI cannot add functions, so that extensibility is not an attack path.
	
	AC: a test shows that no protocol method reachable by `ai` writes to the function folder, executes code, or changes help topics.
	
	Use case: PLATFORM · Decisions: D38 · **The dispatch-level guarantee now holds (SEC-10, fixed 2026-11-06):** `MethodTable.dispatch` refuses any write method outside `Account.allowed_methods`, whatever engine or path reaches it, and `apply` separately refuses `account.system` unconditionally. The story's literal AC (a function folder, code execution, help topics) is still moot — none of those exist yet — but the mechanism this story would be tested against is in place.
- [ ] **E8.1 · Desktop installers**
	As a user, I want a normal installer per OS with the interpreter inside, so that I never install Python myself.
	
	AC: built on E0.6; signed and notarized where required; uninstall leaves no processes or services.
	
	Use case: PLATFORM · Decisions: D16, D22 · D98: the installers bundle no TeX; LaTeX is the user's own install. The Windows installer must ensure the WebView2 runtime. On Linux the GTK shell needs GTK 4, libadwaita and WebKitGTK 6.0 plus a Python with PyGObject. Windows signing certificate and Apple developer membership are the owner's decisions.
- [ ] **E8.2 · Install profiles**
	As a user, I want a small client-only install or a full local install with the server, so that I only get what I need.
	
	AC: client-only without pandas/numpy; full install starts its server; sizes measured.
	
	Use case: PLATFORM · Decisions: D36, D38, D42
- [ ] **E9.4 · Layout and pagination**
	As a writer, I want pages that break the same way everywhere, so that printing is predictable.
	
	AC: a decision on the layout approach (server-side layout, or reflow without pages) using the E0.5 measurements.
	
	Use case: ALL · Decisions: D26, D61 · With the full LaTeX engine (D88) server-side layout is real: the page view could show pages typeset by the engine, so page view and PDF match; the cost is latency while typing and a second layout engine beside the flow view. Engines differ per shell, so identical line breaks cannot be assumed. The page view built today is approximate and is not this story.
- [ ] **E9.5 · odt and docx**
	As a writer, I want to import and export OpenDocument text first and Word files second.
	
	AC: import and Save As .odt (first, on the shared ODF layer) and .docx; styles map to named styles; a list of losses; the native format stays.
	
	Use case: ALL · Decisions: D5, D70 · LaTeX import and export are separate stories (E9.19, E9.20); the order among docx and LaTeX is open.
- [ ] **E9.12 · Outline view and side-by-side versions**
	As a writer, I want an outline of my headings that I can rearrange, and two versions of a paragraph next to each other.
	
	AC: the outline lists headings from styles with their text collapsed, and dragging a heading moves its section as a command, for several users at once under the lock rules; a paragraph can have alternative versions side by side, choosing one is a command and the others are kept in the history; an AI alternative arrives as a suggestion.
	
	Use case: ALL · Decisions: D64 · Whether alternative versions live in the document or only in the history is open and needs a design discussion before `ready`.
- [ ] **E9.13 · Optional process help in composes**
	As a writer, I want gentle help for the stages of a document (draft, writing, polishing), without being forced into stages.
	
	AC: a document may have a stage shown quietly, as metadata only and never a gate; draft turns notes into an outline with the AI's help, writing helps fill it, polishing offers the thinking aids; the AI may suggest a stage change with a reason and a dismissal is remembered so it does not nag; when a suggestion is accepted the person is asked once whether it fits her.
	
	Use case: ALL · Decisions: D60, D71 · Ground rule: a user never has to follow the stages.
- [ ] **E9.14 · Page layout definition**
	As a writer, I want page size, orientation, margins, headers, footers and page numbering defined as named page styles.
	
	AC: a page style is a named definition of its own, not CSS text styling; a document uses one or more by section; header and footer text can use fields; the page view and PDF export follow it; ODT and docx export map it.
	
	Use case: ALL · Decisions: D61, D73, D75 · Depends on the pagination decision (E9.4). Official letter layouts are page styles plus text styles in a template.
- [ ] **E9.15 · Bibliography model in BibTeX**
	As a researcher, I want my document to hold its bibliography as BibTeX entries.
	
	AC: entries are commands in the log (add, change, remove), undoable and visible in the history; import and export of a `.bib` round-trips field for field, including fields and entry types Claudia does not know, keeping comments and `@string`; citation keys unique, a clash reported and resolved by the person; the entry keeps the original BibTeX text and the display shows decoded text; a bibliography view with search, sort and "cited / not cited"; entries are content-domain data, not shared across documents.
	
	Use case: SCI, EDU, ALL · Decisions: D86, D15, D21 · Proposal: BibTeX types and fields as the base, biblatex extras accepted and kept, nothing dropped. Redaction must be able to remove an entry's text.
- [ ] **E9.16 · Citations and the reference list**
	As a writer, I want to cite an entry and have the reference list built in the style my field uses.
	
	AC: insert a citation from a search over the bibliography, as an inline mark referring to citation keys; the reference list is derived and updates when entries or citations change; named citation styles chosen per document, a few shipped and more installable; clicking a citation shows the entry, a missing key is flagged, unused entries listed; export to ODT/docx fields and to `\cite` plus a `.bib` in LaTeX, with losses listed; AI citations are suggestions.
	
	Use case: SCI, EDU, ALL · Decisions: D86, D62 · The style engine (CSL or biblatex through the engine) is an open decision; the two must not give different lists for the same style.
- [ ] **E9.17 · Reference manager plugins**
	As a researcher who keeps my library in Zotero or Mendeley, I want composes to talk to it.
	
	AC: a bibliography connector is an extension point with the help contract; first connectors Zotero and Mendeley plus a generic `.bib` reader; a connector that needs the local application runs in the client or shell, one that uses a web API sends credentials from the client per request; **API keys and tokens are never stored in the document** and never reach other users; inserting copies the entry into the document's bibliography with provenance, and a changed library entry is only updated after asking; a connector cannot write to the library unless asked, and the AI cannot use one without the person's session; tests with a fake library for each connector.
	
	Use case: SCI, EDU · Decisions: D86, D29, D38, D72, D20 · Depends on E9.18. Do not use Zotero or Mendeley logos or wording that suggests endorsement.
- [ ] **E9.18 · Spike: Zotero and Mendeley integration**
	As a developer, I want to find out what Zotero and Mendeley really offer for reading a library, so that E9.17 rests on facts.
	
	AC: per application, which interfaces exist today, what they need installed, rate limits and terms of use, the licence of any client library, and whether the interface works from a browser page, a desktop shell and a server; a small prototype per application that lists the top level of a library and fetches one entry as BibTeX, tested on all three OSes; a recommendation and the data a connector must store on the client.
	
	Use case: SCI · Decisions: D86 · Marked `ready` in the old backlog and never started. Must not assume Mendeley has a usable third-party interface or that Zotero's local interface works in every setup.
- [ ] **E9.19 · LaTeX export**
	As a researcher, I want to save my composes document as a LaTeX project.
	
	AC: Save As produces a zip with a main `.tex`, the bibliography as `.bib`, the figures as files and any needed class or style files, needing no network; a documented mapping with a list of losses; the export compiles with the engine as a test of every release, with a fixture document using every construct; authorship, suggestions and comments are not exported by default; the same engine produces the PDF from the same `.tex`.
	
	Use case: SCI, EDU · Decisions: D87, D70, D88 · Open: which classes first; where this sits against docx.
- [ ] **E9.20 · LaTeX import**
	As a researcher with an existing LaTeX document, I want to open it in composes.
	
	AC: import of a `.tex` project mapping sectioning, paragraphs, emphasis, lists, simple tables, maths, figures, footnotes, cross-references, citations and the bibliography to named styles and inline marks; **what is not understood is kept as a raw LaTeX block**, typeset and shown as an image, editable as source and exported unchanged, with every such block listed in the import report; a project that does not compile is imported as far as it parses with the error shown; missing packages listed; nothing fetched from the network; tests with real documents.
	
	Use case: SCI, EDU · Decisions: D87, D88 · Probably the hardest import in the suite; the first version should accept a defined subset and be honest about the rest.
- [ ] **E10.2 · Understated presentation mode**
	As a presenter, I want an elegant, laid-back presentation mode.
	
	AC: full-screen mode, minimal transitions, speaker view, the same on web and desktop.
	
	Use case: EDU · Decisions: D1
- [ ] **E10.3 · odp and pptx**
	As a presenter, I want to import and export OpenDocument presentations first and PowerPoint files second.
	
	AC: import and Save As .odp (first) and .pptx; masters and layouts map to the template model; unknown shapes map as in E10.7; a list of losses; the native format stays.
	
	Use case: ALL · Decisions: D5, D67, D70
- [ ] **E10.4 · Templates, slots and layouts**
	As a presenter, I want slides made of typed content placed into a layout from a template, so that content and form are separate as in LaTeX.
	
	AC: a template defines page format, colours, fonts, styles and a set of layouts with typed slots; a slide is its content in slots plus the name of its layout, and changing the layout re-flows the slots without moving free-floating objects; page number, footer and title style belong to the template and cannot be edited on a slide; a deviation is a new named style made through the shared dialog; a style or template change is a command, and changing the template restyles every slide; creating a deck starts from a template or from "What would you like to achieve?".
	
	Use case: ALL · Decisions: D68, D62, D73, D67 · **Needs a design discussion with a mock-up before `ready`;** the owner is not sure how users should work with templates. The slot and layout model also decides the import mapping for pptx and odp.
- [ ] **E10.5 · Template provenance on every slide**
	As a presenter, I want every slide to show which template and layout it comes from and what is inherited.
	
	AC: a badge or panel on the selected slide names the template, the layout and any named variant, showing inherited properties as inherited with a link to change them in the template; trying to edit an inherited item explains where it is defined and offers to open the template or create a named variant; a list of slides that deviate from their layout.
	
	Use case: ALL · Decisions: D68 · The direct answer to PowerPoint's master-slide confusion; usability-test it with people who know PowerPoint.
- [ ] **E10.8 · Images and figures**
	As a presenter, I want to place JPEG, PNG, GIF, SVG and other figures.
	
	AC: JPEG, PNG, GIF (animated in presentation mode, still in page view), SVG, WebP and AVIF as far as the shell engines support, with a table per engine; other formats converted on the server or refused with a reason; **SVG from outside is always shown as an image, never inline**, and scripts and external references are stripped on export; images are content-addressed assets with alt text required by a prompt; the same image model is reused by composes and computes.
	
	Use case: ALL · Decisions: D67, D66 · Huge images need size limits and downscaling on the server.
- [ ] **E10.9 · AI thinking aids in creates**
	As a presenter, I want the AI to point out clutter, poor wording and structure problems, and propose colours and fonts from my purpose.
	
	AC: on request the AI reports cluttered slides, poor word choice, spelling and deck structure as comments in the panel, and may propose changes as suggestions; given the stated purpose it proposes a colour scheme and fonts as a named template variant, never silently applied; the rules for what counts as clutter are listed and tunable per document.
	
	Use case: ALL · Decisions: D64, D24 · Needs a rendering of the slide for vision-capable models or a structural description for small ones; decide in E7.5.
- [ ] **E10.10 · Audience, purpose and story structure**
	As a presenter, I want help deciding who a presentation is for, what it should achieve and how to structure it.
	
	AC: when started from "What would you like to achieve?", the AI asks about audience and purpose and proposes a story arc as an outline of slide titles that the person edits; nothing is created without confirmation; each outline item can later be linked to the slide that realises it; all of it is optional.
	
	Use case: ALL · Decisions: D60, D68, D71
- [ ] **E10.11 · Connected thoughts**
	As a presenter, I want to lay out my thoughts as a connected map and turn a thought, or a chain, into slides.
	
	AC: a thought map view in the frontend; a node or a path becomes a slide or a sequence in a chosen layout, and the slide keeps a link to its node; the map and the slide order stay in sync through commands, not two stores; presentation mode can later follow a path instead of the slide order.
	
	Use case: EDU, SCI · Decisions: D68, D58 · Inspired by Prezi; the zooming canvas itself is not a goal. A thought map could share a model with the composes outline (E9.12).
- [ ] **E10.14 · Export to LaTeX Beamer**
	As a presenter who works with LaTeX, I want to export my deck as a Beamer project.
	
	AC: Save As produces a zip with a Beamer `.tex`, the images, the bibliography where the deck cites, and the shapes as TikZ, compiling with the engine as a release test; a documented mapping with losses (slide to frame, slots to Beamer constructs, template to a theme, shapes to TikZ paths, free-positioned objects to absolutely placed nodes, speaker notes to notes); unmappable objects replaced by a first frame and listed; Beamer import is not part of this story.
	
	Use case: SCI, EDU · Decisions: D87, D67, D88 · The few-shapes policy and the path format make this tractable. Depends on E10.4 and E3.10.
- [ ] **E11.2 · Licence audit**
	As the project owner, I want every dependency checked against the GPL-near goal.
	
	AC: a list of components with licences; conflicts flagged (fonts, TeX engine and package set, citation style engines and style files, reference manager client libraries, model licences, icons).
	
	Use case: PLATFORM · Decisions: D14 · Already has named open questions waiting on it: the licence of Latin Modern and TeX Gyre (believed GUST Font License) is unverified, Mermaid's licence and bundle size are unchecked, and the `cryptography` package's compatibility with GPL-3 was marked "to confirm".
- [ ] **E11.3 · Name check**
	As the project owner, I want to know whether "Claudia" collides with trademarks or products.
	
	AC: a search result note and a go/no-go recorded.
	
	Use case: PLATFORM · Decisions: D1 · D1 was taken knowing the name is close to "Claude"; the design notes mention an unrelated open-source project of that name. Cheap to do and gets more expensive to act on the longer it waits.
- [ ] **E12.1 · "What would you like to achieve with this document?"**
	As a user, I want to be asked, if I like, what I would like to achieve, and have Claudia derive goal, audience and a process from my answer, without being forced to have a goal.
	
	AC: an optional prompt offered at creation and any time from the panel, skippable and switchable off; the AI proposes goal, audience, purpose and a per-app process as suggestions the person edits, accepts or dismisses; goal, audience and stage are **document metadata at most**, stored as logged commands in the content key domain, shown quietly, editable by hand, used as AI context, with no feature depending on them; a dismissed suggestion does not reappear; a document with no goal behaves exactly as today.
	
	Use case: ALL · Decisions: D59, D60, D71 · Careful with AI-derived goals: show them as the AI's reading, to be corrected.
- [ ] **E12.2 · Embeds with provenance, updated only on request**
	As an author, I want to insert a result from another document and keep a link to its source, so that the evidence travels with the story.
	
	AC: the person's client opens both documents and pulls a rendered result into the target; the embedded item carries document id, server, range or chart name and the source revision, shown on hover and in a list of sources; **updates only happen after asking**, with the prompt showing what changed and "not now" remembered until the source changes again; no server-to-server access and no shared keys; works between all app pairs and within one app, as an undoable command; if the source cannot be opened the item keeps its last content and says why.
	
	Use case: ALL · Decisions: D58, D65, D72, D20, D34 · Revision ids can change meaning after a restore, so provenance must record the line too. Needs a cheap way to ask a source for its latest revision.
- [ ] **E12.3 · Turning material from one app into another**
	As a thinker, I want help moving an insight from computes to a write-up or a presentation, and a text to a presentation.
	
	AC: "Write up what this model shows" creates or extends a composes document with a summary, the key chart and numbers as embeds and a plan for explaining the steps of thought, as suggestions; "Make a presentation from this text" proposes an outline of slides from headings and key claims, then builds slides once confirmed; the AI works with sessions in each document under the asker's rights; the new document gets provenance links and optionally its own goal; never automatic.
	
	Use case: ALL · Decisions: D58, D64, D65, D72 · The clearest expression of D58, the suite's reason for being. Needs E7.x, E9.1, E10.1 and E6.x.
- [ ] **E12.4 · Claims and evidence**
	As an author, I want to link a statement that cites a number to its source, and have the AI check they agree and ask what a sceptical reader would ask.
	
	AC: a statement can be linked to a source via an embed or a reference, optionally; on request the AI compares text and data and reports mismatches as comments or suggestions, flagging statements with numbers and no link; "play a sceptical reader" produces the questions an audience would ask, as a reading in the chat, never a gate; a claim whose source changed is marked "check again", not changed.
	
	Use case: SCI, FIN, EDU · Decisions: D58, D64 · Quality depends on the model; show the reasoning so a person can disagree.
- [ ] **E12.5 · Mermaid and LaTeX in all three apps**
	As an author, I want to write a LaTeX formula or a Mermaid diagram as text and see it rendered in all three apps.
	
	AC: an insert action per app takes LaTeX or Mermaid source, shows a live preview and renders in the document, with the source editable and the truth; a text block can be set to LaTeX text for typeset paragraphs; the rendered SVG is stored as a content-addressed cache so exports need no browser, rebuilt when the renderer version changes; LaTeX goes through the full engine, Mermaid runs in the frontend at strict security level, and rendered output is always an image, sanitised on export; errors shown next to the source with the line, never blocking saving; bundled offline, sizes measured, fonts via the font service.
	
	Use case: ALL · Decisions: D66, D30, D88 · Mermaid's licence and bundle size are to check (E11.2).
- [ ] **E12.6 · OpenDocument formats first**
	As a user and as a public organisation, I want to import and export ODT, ODS and ODP.
	
	AC: one shared ODF layer for packaging, styles, embedded images and metadata, with app-specific mapping in E9.5, E6.9 and E10.3; export and import for all three apps come before the Microsoft formats; each import lists what could not be kept and each export is checked by opening it in LibreOffice; **the native format stays** and open-format exports contain the current state only, which the dialog says; named styles map to named ODF styles and templates to master pages, with every export listing what could not be mapped.
	
	Use case: ALL · Decisions: D5, D19, D70 · Whether public administrations require ODF is to verify per country.
- [ ] **E12.7 · Public administration and schools**
	As an administrator or teacher, I want Claudia to be accessible, self-hosted and ready for official documents.
	
	AC: accessibility goals written down against a chosen standard and tested per release; exported documents carry structure and alt text; a plain-language check as an AI thinking aid for German and English first, switchable and never automatic; official templates as installable packages; a self-hosting guide with an overview of data flows for a data-protection officer; requirements collected from at least one real administration and one school before the stories are cut.
	
	Use case: EDU, ALL · Decisions: D69, D5, D70 · The accessibility half is blocked by E5.10 and the open bugs UX-01 to UX-05.
- [ ] **E13.3 · Help service**
	As a client or the AI, I want to search help and fetch topics from the server, so that help is the same in every shell and works without a network.
	
	AC: versioned endpoints for search by text, lookup by id, lookup by context and the topics of an extension, answering in the person's language with fallback to English; full-text search over titles, tags, body and examples (SQLite FTS5 proposed), ranked by app and context, finding topics by what they explain; rendered topics cached by content hash and language, with the source available to the AI; works offline and for every role, needing no document key; built-in help bundled with the server, extension help from the extension folder.
	
	Use case: ALL · Decisions: D76, D30, D31 · Depends on E13.1 and E13.2.
- [ ] **E13.4 · The AI uses help as its knowledge base**
	As a user, I want to ask the AI how to do something and get an answer based on Claudia's own help.
	
	AC: the `ai` user has read-only help tools for every role; for a "how do I" question it looks in help first, answers from the topics it found and **names them**, and says so honestly if nothing fits rather than inventing a feature; topics are short enough for a small local model to read whole; **help text is data, not instructions** — text from extensions is passed as untrusted content and a test shows an instruction inside a topic is not followed; the skill files tell the AI to use help first; the AI cannot change help.
	
	Use case: ALL · Decisions: D76, D24, D32, D56 · The prompt-injection test here is the same boundary question as SEC-10 and should be built with it.
- [ ] **E13.5 · Help in context**
	As a user in the middle of doing something, I want help for exactly this, one step away.
	
	AC: hovering a menu item, toolbar button, function name or dialog control shows its tooltip; a key and a "Help on this" context item open the topic for what is selected or focused; while a formula is typed the formula bar shows the signature and a short example of the function under the cursor; **every action in the manifest carries a help topic id and a test fails when one has none**, likewise for dialogs; Help ▸ Help opens the help view with a search field as a tab of the docked panel, never an overlay; "Ask the assistant" starts a chat with the topic or query as context; the same behaviour in every shell, keyboard operable and readable by assistive technology.
	
	Use case: ALL · Decisions: D76, D40, D44 · Where the help view lives is a design question; the panel tab is a proposal. The key must not clash with the native F1 of the shells.
- [ ] **E13.6 · Core help content**
	As a new user, I want "how do I" topics for the everyday things in each app.
	
	AC: a first set per app written to the author guide, covering computes (enter and fill a formula, name a range, a SQL cell, a chart, a slider, precedents), composes (apply and name a style, suggestions, insert a formula or diagram, page view), creates (choose a template, change a layout, lock a shape, insert a figure) and all (share a document, add a user, save a checkpoint, restore with consent, ask the AI, import and export); **every user-visible action and dialog has a topic** and every built-in function a tooltip and a topic with an example; each example checked by E13.9.
	
	Use case: ALL · Decisions: D76 · Written alongside the features, not after: a story that adds a visible action is not done without its topic — to add to the definition of done in `CONTRIBUTING.md`.
- [ ] **E13.7 · Try-it examples**
	As a learner, I want to run an example from a help topic on a copy, so that I see how it works and then use it.
	
	AC: an example block can be opened as a live example — in computes a small sheet beside the topic where the formula is evaluated and its inputs changed, in composes and creates a scratch document; "Use this" copies the example into the person's document as an ordinary edit; the live example runs on the throwaway overlay and never writes to the person's document or log.
	
	Use case: EDU, ALL · Decisions: D76, D33 · Depends on E4.8. A good place for Claudia's character; not needed for the first version.
- [ ] **E13.8 · Translating help**
	As a translator, I want help topics to be translatable like the interface.
	
	AC: topics have a language and a link to the source topic they translate, a translation older than its source is flagged, and search falls back to English; translators use the same catalog tooling as the interface or topic files; the AI can answer in the person's language from the English topics, naming the topic.
	
	Use case: ALL · Decisions: D76, D31 · Help is larger than the interface text; machine translation proposed by the AI could help but must be reviewed by a person.
- [ ] **E13.9 · Help checks in CI**
	As a maintainer, I want automatic checks of the help, so that help does not rot.
	
	AC: part of `scripts/check_debt.py` — every topic renders, every example runs and gives the stated result, links to actions, functions and other topics resolve, no action or function lacks a topic or tooltip, stale topics are listed; the same check runs at load time for extensions, reporting to the admin; failures name the topic file and the line.
	
	Use case: PLATFORM · Decisions: D76, D39


## doing

- [ ] **E0.1 · libadwaita window on Linux (Windows and macOS: fallback evidence)**
	As a developer, I want a minimal libadwaita window with a header bar, the four menu buttons and an About dialog on GNOME/Linux, so that we know the GNOME look of the Linux shell is achievable.
	
	AC: runs on GNOME/Linux with header bar, menu buttons, `Adw.AboutDialog`, file chooser, clipboard, dark mode, HiDPI and a text input method working, or each failure written down; install size and cold start time recorded.
	
	Use case: PLATFORM · Decisions: D3, D4, D22, D28, D42
	
	Status evidence: Linux headless probes pass on system Python 3.12 and CPython 3.14.6 (7 of 7); a screenshot shows a GNOME-looking window. A Windows 11 quick check with the MSYS2 toolchain passed all 8 checklist rows by hand. **Not done:** a run on a real GNOME session (HiDPI, input method, Wayland), the Windows bundle (first script failed silently, rewritten, never re-run), Windows 10, macOS. The real Linux shell now exists under `clients/linux/`, which makes most of this story's Linux half moot, but the bundle criterion has been met on no OS.
- [ ] **E0.2 · Embedded server and worker processes in the bundle**
	As a user on localhost, I want the desktop app to start its own bundled server and worker processes, so that nothing has to be installed by hand.
	
	AC: the bundle starts a minimal WebSocket server with the bundled interpreter and the client connects over localhost; a warm pool of worker processes starts in the bundle on all three OSes, runs a pickled function and is killed on timeout; clean shutdown with no orphan processes after quitting or crashing the window.
	
	Use case: PLATFORM · Decisions: D16, D37, D38
	
	Status evidence: Linux 20 of 20 scenarios pass, also from a relocated copy (bundle about 115 MB). **Windows and macOS not run.** Findings worth keeping: busy workers need a parent-sentinel watchdog (a negative control left 3–4 processes behind without it); Python 3.14 aborts at exit if a daemon thread blocks in `sys.stdin.buffer.read()`, so the lifeline reads the descriptor with `os.read`; killing busy workers first cut shutdown from 4.3 s to 0.3 s.
- [ ] **E0.3 · Shells: GTK with WebKitGTK 6.0 and Neutralino**
	As a user on Linux, Windows or macOS, I want the Claudia frontend and a Plotly chart in a desktop window that behaves like a normal app of my OS.
	
	AC: a prototype of the shell contract implemented by a GTK 4/libadwaita shell with WebKitGTK 6.0, a Neutralino project with the OS title bar and native menu, and a plain browser stub; one test page with bundled plotly.js running in all three (bar, line, 100k `scattergl`, heatmap, a `@font-face` label) with hover, zoom and click, at 100% and 150% scale; tested on Windows 11, a clean Windows 10 22H2, current and older macOS, and GNOME on Wayland; window behaviour, menu mapping, native-API security, server start and stop with no orphans, install size and start time per OS; a maturity check of Neutralino and a named fallback shell.
	
	Use case: DATA · Decisions: D22, D33, D40, D41, D42, D43, D44
	
	Status evidence: the GTK half has since become a real shell (`clients/linux/`), run headless with all automatic checks passing. **Neutralino 6.8.0 has now been run** (2026-11-07, `spikes/e0-3-neutralino/`, notes in `notes/e0-3-neutralino-windows-macos.md`) on one Mac (WKWebView) and one Windows 11 machine (WebView2): all automatic checks pass on both, including Plotly 3.7.0 bar, line, heatmap and 100,000-point WebGL (first WebGL draw on macOS 857 ms, later 50 ms), a native menu from a manifest, native file dialogs, theme, and starting and stopping a server process. Found and solved: the `NE_CL_IVCTOKN` token error (a second Neutralino script tag clears the one-time token; D157). Needed in the shell: Edit roles and accelerators on macOS, and printing through the shell (D158). **Not done:** a clean Windows 10 22H2 and the WebView2 runtime, GNOME on Wayland, an older macOS, the maturity check of Neutralino and a measured install size and start time, a real round-trip time of the bridge (the first number was a no-op), a Windows leftover-process check, and **how the real frontend reaches a Neutralino shell given D115 (D159)**. **No Plotly chart exists in the real frontend**, so the criterion that motivated the architecture is still untested there.
- [ ] **E0.4 · Typesetting service spike**
	As a developer, I want to compare LaTeX renderers on real samples, so that we pick the engine for help pages, tooltips and formula pop-ups.
	
	AC: about 20 sample formulas and 5 sample help pages rendered by KaTeX or MathJax, MicroTeX and Tectonic, recording render time, SVG quality, bundle size, offline operation, behaviour on all three OSes and shell-escape settings; **for D88** a full-document test with a sample article (sections, lists, tables, figures, `amsmath`, citations through BibTeX and through biblatex/biber) and a Beamer deck compiled offline by each candidate that can, recording the offline package set and how it is curated, compile time warm and cold, memory, bundle size, the PDF-to-SVG route and the sandbox; **for the preview question** the latency of a single formula in the full engine against KaTeX or MicroTeX.
	
	Use case: PLATFORM · Decisions: D30, D88, D91
	
	Status evidence: one probe on one Linux machine with Debian TeX Live 2023: formula to PDF 0.15 s (pdflatex) and 0.32 s (xelatex), PDF to SVG 0.03 s, peak memory about 183 MB — so a full engine is probably fast enough for formulas. Sandbox flags stop `\write18`, absolute and `..` reads and writes outside the job. XeTeX ignores fontconfig aliases (D95). **Not done:** Tectonic, KaTeX/MicroTeX, every full-document test; that machine had no biblatex, biber, dvisvgm or tectonic, so biblatex and Beamer-with-biber remain untested.
- [ ] **E0.7 · Baseline for the demo's recalculation**
	As a developer, I want to measure how recalculation scales, so that "quadratic in formulas" is a number and E4 has a target.
	
	AC: time per edit for sheets with 1k, 10k and 100k formulas (simple chains, fill-down columns, range sums, lookups); a result table stored with the analysis.
	
	Use case: DATA · Decisions: D37
	
	Status evidence: measurements exist for the new engine, not for the demo it was meant to baseline: parse ~25–59 µs, paste ~90 µs per formula, one edit in a 50k-row workbook with range readers ~0.25 ms (16.7 ms before the block index), a 20k-deep chain ~0.3 s, and **inserting a row in a workbook of 100k formulas ~12 s**. Six scaling guards run in the gate. The last number is the open target (PERF-07).
- [ ] **E0.8 · Text input in the shells' web views**
	As a developer, I want to type into editable fields in each shell's web view, so that we know where the web frontend's text input and accessibility fall short.
	
	AC: a `contenteditable` page and a plain text field run in the GTK shell, the Neutralino shell on Windows and macOS, and a browser; tested with German dead keys and AltGr, an input method with its candidate window, copy and paste of plain and rich text, spellcheck, drag and drop, and the native Edit items and shortcuts reaching the field; a screen reader (Orca, NVDA, VoiceOver) reads the field and announces caret moves; failures written down.
	
	Use case: PLATFORM · Decisions: D41, D42 · Needs real machines with real input methods. Feeds E9.3 and E6.3.
	
	Status evidence: **Linux:** the client notes say only Xvfb was available, with no D-Bus session bus; input methods, screen readers and portal dialogs were not checked. **Neutralino, 2026-11-07 (one Mac, one Windows 11; `notes/e0-3-neutralino-windows-macos.md`):** German dead keys and AltGr ok on both (on macOS typed apostrophes came back as curly quotes, cause not investigated and unknown for `<input>`); input method ok on Windows, **not tested on macOS**; clipboard of plain and rich text ok on both after macOS needed Cocoa `action` selectors on the Edit items; spellcheck and context menu ok on both; drag and drop of text ok on Windows, not filled in on macOS; native Edit items reach the field. **Screen readers not tested on any OS.** Still open: all of Linux, VoiceOver, NVDA, and a clean Windows 10.
- [ ] **E1.8 · Redaction semantics**
	As an owner, I want to redact commands, so that a leaked secret can be removed from the history.
	
	AC: a redacted command keeps its kind, ids and place in the order but loses its content; the redaction is itself logged without the content; later replay is deterministic; hooks tell caches, undo stacks, AI memory and assets to purge.
	
	Use case: ALL · Decisions: D21, D34
	
	Status evidence: `Document.redact` with purge hooks exists and is tested, including a rolled-back unsafe redaction. **Open (the owner is thinking about it):** the redaction contract — what `redacted()` must keep for later commands to replay; today the default is a no-op tombstone and a redaction that breaks replay is rolled back with an explanation. **And the file does not honour it:** the container never rewrites blocks or the journal, so the bytes remain (SEC-05). Hidden side lines must be redactable too, or a secret that exists only on a hidden line cannot be removed.
- [ ] **E1.9 · Document manifest and requirements**
	As a server, I want a manifest that declares the app type, schema versions, fonts and UserFunctions a document needs, so that I can check and provide them on open.
	
	AC: opening a document with a missing function or font produces a precise report; fonts are offered by the font service; a function digest mismatch marks affected results stale.
	
	Use case: ALL · Decisions: D26, D38
	
	Status evidence: `claudia_core.manifest` holds the data model and the check. The services behind it are not wired: `providable_fonts` is not in the check, the font service has no routes (E3.3), and there is no function folder (E4.10).
- [ ] **E1.10 · Style model in the kernel**
	As an app developer, I want one style model (named styles whose properties are CSS, with inheritance and commands) in the kernel.
	
	AC: a style has id, name, kind, optional parent and a set of CSS properties, storing only its differences, with no cycles; **only an allow-list of CSS properties and value types is accepted** — no `url()`, `@import`, `@font-face`, external references, scripts or outside `var()` — refused when the command applies, naming the offending property, and versioned like command schemas; commands create, rename, change, deviate, delete and apply, all logged and undoable per author; names unique inside a document; changing a parent changes every child that has not overridden; **deleting a style never changes how anything looks and never leaves a dangling reference**, with the person choosing "keep their look" or "re-base on another style", and root, built-in and template styles only hideable.
	
	Use case: PLATFORM · Decisions: D73, D75, D62, D15, D21
	
	Status evidence: built as `claudia_core.css` (`CSS_VERSION` 1, `validate_css`, `parse_css` with line-numbered problems, `format_css`) and `claudia_core.styles` (`StyleDef`, `StyleBook` with `based_on` inheritance, `CreateStyle`, `ChangeStyle`, `RenameStyle`, `RemoveStyle`, `StylesChanged`), with two-author conflict tests. **Not done:** `kind` (only paragraph styles exist), the full delete rules (`RemoveStyle` exists only as the undo of a create), upcasting of dropped properties, and the style kinds for cells and shapes.
- [ ] **E2.1 · Container format**
	As a user, I want my document as one compressed file, so that it is small and easy to move.
	
	AC: a ZIP container with manifest, command blocks, content-addressed assets and an optional snapshot cache, with a format specification; atomic writes, so a crash during editing loses at most the journal tail; a write-ahead journal folded into the container when the document is idle or closed; a small plain part of the manifest readable without any password, so the server can list sealed documents.
	
	Use case: ALL · Decisions: D19, D15, D103, D106
	
	Status evidence: nearly all of it is built in `claudia-container`: the zip with `format`, `manifest.json`, `slots.json`, `people.bin`, `head.bin`, `content/snapshot.bin` and `history|chat/NNNNNN.blk`; blocks framed, zlib-compressed and AES-256-GCM sealed with additional data naming document, domain, number and the previous block's hash; a head record detecting removed or extra blocks; atomic replace; a journal with CRC and torn-tail repair; reader limits against zip bombs, `..` paths, duplicate names and lying sizes. **Not done:** the format specification in `docs/`; packing still rewrites the whole zip (PERF-06); an older copy of the whole file can still be put back.
- [ ] **E2.2 · Key slots**
	As an owner, I want several passwords to open one document, so that roles can have their own.
	
	AC: each password derives (Argon2id) a key that unwraps the domain keys of its role; changing a password rewraps the keys without re-encrypting content; an optional recovery key, with it documented that a lost password without one means a lost document; known-answer tests and a review of the scheme.
	
	Use case: ALL · Decisions: D19, D20, D34, D101, D102, D104, D105
	
	Status evidence: built in `crypto.py` and `slots.py` — Argon2id with bounded parameters, HKDF with distinct labels, a locator derived from name *and* password so names never appear in the file, password change, and a recovery key (13 groups of 4 base32 characters, shown once). Known-answer tests from RFC 5869, RFC 9106 and the GCM vectors. **Not done:** an external or structured review of the scheme (part of E2.8); key rotation; and the KDF cost is uncalibrated — the default measures about 0.09–0.4 s against the 0.5 s target of D109.
- [ ] **E2.3 · Users and roles inside the document**
	As an owner, I want to add users (name, password, role) to my document, so that the history shows who really did what.
	
	AC: roles owner, editor and viewer; adding, removing and changing users; the name `ai` is protected; no central user database anywhere.

	Use case: ALL · Decisions: D20, D35, D55, D101, D142, D143, D144

	Status evidence: the directory now lives inside the document (`people.bin`, sealed with the content key) and `SealedDocuments` is both the provider and the user directory; `add_user` is owner-only and `ai` is refused. Two role changes are now built without remove-and-re-add: anyone can leave on their own (`leave_document`; needs none of the three domain keys, unlike `remove_user`) and an owner can hand ownership to an existing editor through a two-password propose/accept handshake (`transfer_owner`, time-limited, server-memory-only) — both reachable from File ▸ Manage (Leave document…, Assign new owner…, Accept ownership…) in all three apps, web and GTK. **Not done:** changing any other role (editor↔viewer) without removing and re-adding the person; key rotation; who may discard side history after a restore.
- [ ] **E2.4 · Key domains and visibility**
	As an owner, I want viewers to read the document but not its history or chat, so that sharing a file does not share everything.
	
	AC: domains content, history, chat; a viewer password opens content only; **the server enforces the same while live**; tests with a file in the hands of each role.
	
	Use case: ALL · Decisions: D34, D101, D111
	
	Status evidence: the file half is built — `slots.py` gives a viewer the content key only, and tests show a viewer's key cannot decrypt history or chat blocks. **The live half is not:** `HostedDocument._audience` in `hub.py` filters only by author (history), by recipient (private chat) and by sender (ephemeral). There is no role check, so **a connected viewer still receives every command, history entry and chat message.** Also still open: a viewer cannot be the first to open a sealed document, which needs a read-only hosting of the snapshot.
- [ ] **E2.5 · Command blocks**
	As an operator, I want commands grouped into compressed, encrypted blocks, so that the file stays small and redaction is cheap.
	
	AC: a block size policy; appending without rewriting old blocks; the compression ratio measured against per-command encryption on real logs.
	
	Use case: ALL · Decisions: D34
	
	Status evidence: blocks are built (about 1 MiB each, framed, zlib-compressed, sealed, chained by hash). **Not done:** the size policy as a stated decision, the measurement against per-command encryption, and appending without rewriting — packing writes the whole zip again.
- [ ] **E2.7 · Open and seal**
	As an operator, I want the server to hold a document's keys only while someone has it open.
	
	AC: keys live in memory only; sealed on last leave and on idle timeout; wrong-password attempts are rate limited; keys never appear in logs.
	
	Use case: ALL · Decisions: D20, D34
	
	Status evidence: keys are pending after login, held while open and dropped by `release`; a byte scan of the folder after packing finds no names, passwords or chat text; the `sealed` close code (4423) tells a viewer to try again later. Hashing runs off the event loop behind a cap (SEC-03). **Not done: rate limiting.** The waiting caps bound how many sockets queue, but nothing slows a patient guesser who fails and reconnects (SEC-11).
- [ ] **E2.8 · Threat model and security review**
	As the project owner, I want a written threat model and an external or structured review before a first release.
	
	AC: a document covering outsiders with the file, co-editors and the server operator; review findings tracked as stories.
	
	Use case: PLATFORM · Decisions: D34, D100
	
	Status evidence: the threat model is written (D100 and `notes/e2-container-and-encryption.md`), with a table per actor and an explicit out-of-scope list. **The review has not happened.** It must cover what the document list and the plain manifest reveal to someone without a password (D103).
- [ ] **E3.3 · Font service**
	As a user, I want missing fonts delivered automatically, so that a document looks right on any machine.
	
	AC: a library of OS fonts plus downloaded collections with licence metadata; WOFF2 served from our own server, never a CDN; the document's requirements checked on open; Microsoft fonts only where the licence allows, with metric-compatible substitutes.
	
	Use case: ALL · Decisions: D26, D89, D93, D94
	
	Status evidence: the library `claudia-fonts` is built (62 tests): collections with a mandatory licence record, a catalogue by family with a digest and substitution table, refused and replaced fonts hidden from the engine, a WOFF2 cache for redistributable fonts only, `@font-face` CSS with escaped family names, and `fonts.conf` for the engine. **Not built:** the server routes under `/api/v1/fonts`, `providable_fonts` in the manifest check, `fonts.lock` and the fetch command, the starter set, and the web composable — so no document can actually be given a font yet.
- [ ] **E3.4 · Typesetting service**
	As an app, I want to send LaTeX to a shared service and get back typeset output, so that formulas, help pages and whole documents look the same everywhere.
	
	AC: three modes — **math** (a formula), **page** (a snippet or help page) and **document** (a complete `.tex` project to PDF); SVG for math and page, PDF for document plus SVG per page for previews; results cached by content hash, engine version and language; wire methods for submit, status, cancel and fetch, described in `/api/protocol`, used by all three apps and the help system; errors come back with the TeX message mapped to the line of the source; jobs go through the worker pool with a fair queue per document.
	
	Use case: ALL · Decisions: D30, D88, D89, D92, D95, D96, D97, D98
	
	Status evidence: the library `claudia-typeset` is built (147 tests, 24 against the real engine, 8 Windows-only): math and page mode to a checked SVG, content-hash cache, TeX errors mapped to the line of the user's own text, a sandbox mutation-tested against hostile input. **Not built:** document mode to PDF (`NotImplementedError`), the wire methods `submit`/`status`/`cancel`, the per-document fair queue, the worker pool, and the server wiring including the settings for the LaTeX programs. Nothing in the product can typeset anything yet.
- [ ] **E3.6 · Remote-AI boundary**
	As an operator, I want the doc server to dial the AI server and let the AI act as participant `ai` over that socket, so that the AI server can run elsewhere.
	
	AC: the doc server initiates; one multiplexed socket per doc server; `ai` has its own replica and goes through the same protocol and permissions; status events; reconnect.
	
	Use case: ALL · Decisions: D8, D6, D56
	
	Status evidence: the participant is built and real — `Assistant` with a pluggable `Engine`, a scripted stand-in for computes and composes, and a `ModelEngine` that drives a real `LanguageModel` off the event loop. **The boundary itself is not built:** everything runs in process, and `Assistant` attaches through `Account.assistant()` and the server's own method table. Building the socket is also when SEC-10 stops being theoretical, because the engine's output then arrives from another machine.
- [ ] **E3.9 · Document list**
	As a user, I want to see the documents on my server, so that I can open one without remembering its id.
	
	AC: an endpoint lists id, title, app type, last change and size, with no content, user names or history; access follows D103; titles come from the plain manifest so sealed documents can be listed; a document marked unlisted does not appear, and for it "missing" and "wrong password" stay the same answer; creating a document is allowed only to those who may see the list; the list is paged and sorted by last change and the endpoint is rate limited.
	
	Use case: ALL · Decisions: D53, D50, D57, D103
	
	Status evidence: `GET /api/docs` returns `{app, documents}` with a listing cache (PERF-04 fixed), and the access secret gates both listing and creation. **Not done:** `Hub.listing` still returns only `{id, app, modified, online}` — no **title** and no **unlisted** flag, although the container manifest carries both (title is currently set to the document id). No paging, no size, no rate limiting.
- [ ] **E3.10 · Full LaTeX engine as a shared core service**
	As the project owner, I want a complete LaTeX engine so that all three apps can typeset offline.
	
	AC: one engine chosen by E0.4, **offline**, with a curated and pinned package set recorded in every cache key; a **sandbox** with shell escape off, a private job directory, no network and limits for time, memory, output and pages, killed on timeout, with a hostile-input suite showing each is stopped; fonts from the font service; the same behaviour on all three OSes — *changed by D98:* on Windows and macOS the engine is the user's own install, found by a configured path; a document never carries TeX packages or executable code.
	
	Use case: ALL · Decisions: D88, D30, D14, D38, D90, D96, D97, D98
	
	Status evidence: the sandbox is built and is the strongest-tested part of the tree — `run_sandboxed` with TeX flags and a clean environment, an SVG allowlist, a 15-test hostile-input suite against the real engine, and mutation checks proving six tests fail if a flag is weakened. The Windows Job Object layer and the user-configured LaTeX with `diagnose()` are written. **Not done:** a curated and pinned package set, biblatex/biber and Beamer, the worker pool, and **a real run on Windows or macOS — the Windows layer has never executed.**
- [ ] **E3.11 · Server administrators and settings**
	As a server operator, I want named administrator accounts and a settings API — separate from any document's own users — so that I can configure how many documents the server holds, its access secret, and its AI model without editing a config file or guessing whether a running server's settings will stick.

	AC: administrator accounts live outside any document, scrypt-hashed like a document's own users but in their own directory; a server that is reachable beyond loopback and has no administrator yet asks for one on first exposure, and never asks again once one exists; signing in issues a bearer-token session, never a cookie; an administrator can add, remove and change the password of another administrator, and the last one cannot be removed; settings (how many documents, the access secret, the AI model and device, the LaTeX program paths) persist across restarts and are editable through a REST API, each call behind the session; an explicit command-line or environment value always wins for that run but is never written back, so an operator's own deployment config cannot be silently overridden by a change made through the UI; the access secret can be revealed, not just rotated, because unlike a password it must stay recoverable; a settings dialog in each client reaches all of this through the gear icon already in the Open dialog, and the TopBar shows whether the server still needs its first administrator.

	Use case: PLATFORM · Decisions: D20, D35, D50, D103, D151, D152, D153, D154, D155

	Status evidence: Patch 1 (backend) is built and tested — `claudia_server.admin` (`AdminAccount`, `AdminDirectory`, `needs_administrator`), `admin_sessions` (bearer-token sessions, in-memory, lazily expired), `server_settings` (persisted `ServerSettings`/`AiSettings`/`TypesetSettings` under `<state_dir>/admin/`), and `admin_api`'s `/api/admin/*` router (status, setup, login, logout, administrator management, settings, live AI reload, typeset diagnosis), wired into `create_app` and into `cli.py`'s precedence rules for `--max-documents`, the access secret and `--ai`. Four new test files plus CLI-level precedence tests, on top of the full pre-existing suite with zero regressions; ruff, ruff format, mypy, vulture, i18n extraction, the API-surface snapshot and the Sphinx docs build are all clean. **Not started:** Patch 2, the frontend — the Nuxt settings pages themselves, the gear icon in the Open dialog, and the TopBar's indicator for a server still waiting on its first administrator.
- [ ] **E4.6 · UserFunction contract v2**
	As a function author, I want vectorised arguments, ranges with addresses, array results, lazy arguments and volatile functions.
	
	AC: the contract written and versioned; numpy arrays in and out; array results spill and the output range is owned; volatile functions use the stored-draw approach; metadata includes name, description, `get_tooltip`, `get_help` (LaTeX) and a schema version, with tooltip and help mandatory and registered into the help system, a function without them refused at load; old scalar functions still work through an adapter.
	
	Use case: ALL · Decisions: D12, D23, D29, D30
	
	Status evidence: `functions/base.py` has a contract with a mandatory description and at least one `Example`, checked in the tests, and arguments converted by the type hints of `call()`. **Not done:** vectorised numpy arguments, array results and spill (a multi-cell result is `#VALUE!` today), lazy arguments, volatile functions, `requirements()`, and — the part that blocks E13 — `get_tooltip` and `get_help`.
- [ ] **E4.11 · Built-in library through the same interface**
	As a user, I want SUM, IF and friends documented like user functions, so that tooltips, help and autocompletion work for all of them.
	
	AC: the first 100 functions registered through the UserFunction interface or an equivalent registry with tooltip and help; the function wizard lists them; the topics are example-oriented.
	
	Use case: ALL · Decisions: D12, D30, D76
	
	Status evidence: 69 functions are registered through the same interface with a description and at least one example — SUM, PRODUCT, AVERAGE, MIN, MAX, COUNT*, MEDIAN, VAR*, STDEV*, LARGE, SMALL, SUMPRODUCT, COUNTIF(S), SUMIF(S), AVERAGEIF(S), MAXIFS, MINIFS and the number, logic and text families. **Not done:** tooltips and help topics, the function wizard, and the remaining ~31 towards 100.
- [ ] **E5.1 · Menu and action manifest**
	As a developer, I want one manifest for menus, shortcuts and labels, so that GTK and web menus cannot drift.
	
	AC: File, Edit, Tools and Help generated into GMenu XML, a Neutralino main menu and a web menu from one source; labels are translation keys; every action carries a help topic id and a tooltip; Undo and Redo enabled from the person's own undo stack.
	
	Use case: PLATFORM · Decisions: D4, D25, D27, D31, D44, D54, D74
	
	Status evidence: a manifest exists but only inside the Linux client (`clients/linux/src/claudia_shell_gtk/manifest.py` plus `data/webroutes.json`), and it **maps between two different menu structures** rather than generating one: the web app has six menus (File, Edit, Format, View, Tools, Help) against D4's four, and the shell carries them out by clicking the web app's own menus through `shim.js` (D117, UX-09). No translation keys, no help topic ids. **Blocked on the open decision UX-06**: four menus or six. *Added 2026-11-07:* the Neutralino run shows an Edit item needs a **role** (undo, redo, cut, copy, paste, select all) beside its accelerator, which on macOS becomes the Cocoa action and shortcut (D158); `manifest.py` has accelerators in GTK syntax but no role field.
- [ ] **E5.2 · claudia-shell-gtk (Linux)**
	As an app developer, I want a thin libadwaita application shell for Linux that hosts the frontend in a WebKitGTK 6.0 view.
	
	AC: the window layout in GtkBuilder XML; a header bar with menu buttons generated from the manifest; the web view filling the content area; the shell contract implemented including file dialogs, About, theme and the server launcher; no layout code in Python; a start-up watchdog so a failed `activate` exits with a message instead of hanging.
	
	Use case: PLATFORM · Decisions: D3, D27, D42, D113–D119
	
	Status evidence: built for **composes only** — a GTK 4/libadwaita window with native File/Edit/Tools/Help, a History and Chat toggle, `Adw.AboutDialog`, application id `de.claudiaoffice.composes`, a desktop entry, an icon and AppStream metadata; a local server per window started without blocking and ended with it (own process group, `PR_SET_PDEATHSIG`, tested with `kill -9`); 180 tests. **Not done:** computes and creates entry points, native Save As and Open dialogs, a stable port so the page's `localStorage` survives a restart, single-instance behaviour, bundling the frontend and interpreter, and any run on a real GNOME session.
- [ ] **E5.3 · claudia-ui (the Nuxt frontend)**
	As an app developer, I want one shell-agnostic Nuxt frontend for all clients.
	
	AC: a Nuxt layer with a shell-contract client (capability detection, stubs in the browser); a web header bar and menu from the manifest, hidden when the shell shows native chrome; the history and chat panel, dialogs, the restore-consent banner and a shared About component; the same build bundled by every shell; a visual comparison of each screen across the shells.
	
	Use case: PLATFORM · Decisions: D3, D42, D43
	
	Status evidence: the frontend is substantial and shared across all three apps — `DocumentFrame`, `DocumentSession`, the grid, the slide canvas, the text editor, the styling components, the panel, the dialogs; 325 vitest tests and `vue-tsc` clean. **Not done: the web app does not implement the shell contract at all.** The Linux shell drives it by clicking its menus through an injected adapter (D117), so there is no capability detection and no browser stub; the restore-consent banner is built (E3.7); no shared About component; the frontend is not bundled with any shell.
- [ ] **E5.4 · Shared About dialog**
	As a user, I want a good-looking About dialog showing the app's own logo, so that every app feels part of one suite.
	
	AC: one component fed by an app-info record (name, icon, version, authors, licence, links); `Adw.AboutDialog` in the Linux shell and the shared web component elsewhere; works for all three apps.
	
	Use case: PLATFORM · Decisions: D28
	
	Status evidence: `Adw.AboutDialog` is built in the Linux shell, and the shared web component exists: `web/app/components/AboutDialog.vue`, opened from the web menu's `help.about` in the apps. *Corrected 2026-11-07:* the earlier line said no web About existed. Neutralino reports `nativeAbout: false` on Windows and macOS, so there the page's own dialog is the About (it was modal and closed on Escape in the spike; D158). **Not done:** a check that all three apps feed it a complete app-info record (authors, licence, links), and that the Linux shell's version and the web one cannot drift.
- [ ] **E5.5 · App icons**
	As a user, I want a distinct icon for composes, computes and creates.
	
	AC: three icons in GNOME icon style plus symbolic versions, shown in the About dialog, launcher and web favicon.
	
	Use case: PLATFORM · Decisions: D1, D28
	
	Status evidence: all three icons are designed and recorded in `notes/design-system.md` (pen nib on rose, `=` with a wavy bar on teal, a slide with a circle on apricot, plus a three-dot suite favicon), and `AppIcon.vue` exists in the web app. **Only composes has a packaged icon** (`clients/linux/apps/composes/icons/…`); there are no symbolic versions.
- [ ] **E5.6 · History and chat panel**
	As an editor, I want a panel docked on the right with the command history and chat.
	
	AC: docked at the right edge in every client; an arrow on its left border shows and hides it and a key sequence does the same; resizable, with width and visibility remembered; authenticated names, time and readable command summaries; `@name` chat; the same behaviour in every shell; redaction available to owners; at narrow widths it pushes the content aside instead of overlaying.
	
	Use case: ALL · Decisions: D7, D32, D40
	
	Status evidence: built and shared by all three apps (`SidePanel.vue`), with history, chat, `@name` mentions and command summaries, plus a History and Chat toggle in the Linux shell's header bar. **Not done:** resizing, remembered width, the key sequence, and redaction for owners.
- [ ] **E5.8 · Open dialog and connection flow**
	As a user, I want File ▸ Open to show the documents on my server, let me create a new one, and ask for my name and password.
	
	AC: the dialog shows the server's document list (title, app type, last change); open or create; for an unlisted document, open by id; a password prompt; a reconnect banner; the certificate trust prompt carried over from the demo; if the server needs an access secret the dialog asks once and remembers it per server.
	
	Use case: ALL · Decisions: D5, D20, D50, D53, D103
	
	Status evidence: built — the list, create, the password prompt, the reconnect banner, and "I forgot my password" leading to the recovery-key flow. **Not done:** the access-secret prompt, the certificate trust prompt (`TlsPolicy` exists in `claudia-client` but the web app cannot use it), opening an unlisted document by id, and the title and last-change columns, which the listing does not return (E3.9). UX-08 is open against this dialog.
- [ ] **E5.9 · Presence rendering**
	As a collaborator, I want to see where others are, so that we avoid collisions.
	
	AC: coloured region outlines and name tags in computes; a cursor and locked zone in composes; colours consistent across clients.
	
	Use case: ALL · Decisions: D11, D17
	
	Status evidence: built in all three apps — outlines and name tags in computes, carets and ± 3-word zones in composes, coloured outlines and name tags on held objects in creates, with one palette (`lib/palette.ts`, the `ai` user Iris). **Not done:** a drag is only seen when it ends (creates), locks are per user name rather than per connection, and the presence update is suppressed while editing because it clashed with the cell lock.
- [ ] **E5.12 · Shell contract**
	As a developer, I want the contract between frontend and shell written and versioned.
	
	AC: a specification of capabilities, messages and errors with JSON schemas; capability discovery; contract tests run against the GTK shell, the Neutralino shell and the browser stub.
	
	Use case: PLATFORM · Decisions: D42, D114
	
	Status evidence: v1 exists as a JSON schema (`clients/contract/shell-contract.v1.schema.json`) with the Python side (`contract.py`, `bridge.py`): `hello`, `welcome`, `action`, `action_state`, `error`, a 64 KiB limit, unknown types ignored and version negotiation (D114). **Not done:** the frontend half — the web app does not speak it (D117), so there are contract tests against the GTK shell only, no browser stub and no Neutralino. *Added 2026-11-07:* the Neutralino spike used its own request/response bridge, not this contract; additive changes it points to are a **print** request (D158) and an Edit **role** on menu items, and a Neutralino transport for the web app's `ShellBridge` (D159).
- [ ] **E5.13 · Shared styling dialog**
	As a user of any app in any client, I want the same dialog for styling text, backgrounds and cells.
	
	AC: one frontend component used by all three apps in every shell, not three dialogs; **step 1 the main path, choose a style** from a gallery with live previews, grouping by purpose, search and the current style marked; **step 2 visibly secondary, deviate** — "Change this style…" for every use and "Deviate…" for a new style with a provisional name, with naming offered but optional and no anonymous one-off formatting; only the properties that make sense for the selection; opened from the toolbar, context menu and a shortcut, fully keyboard-operable; locks respected; every change a command in the history.
	
	Use case: ALL · Decisions: D73, D75, D62
	
	Status evidence: built as an app-agnostic component set talking to a `StyleHost` (`Popover`, `StyleMenu`, `StyleSpec`, `StyleColorPicker`, `StyleFontPicker`, `StyleSizeField`, `StyleCssEditor`, `StylesDialog`), with a Controls|CSS switch, server-side validation while typing with line-numbered errors, a name invitation shown once per style, and the deviate-by-default rule. **Only composes has a host:** computes cells and creates shapes have none, so it is one dialog used by one app. Also not done: search and grouping in the gallery, keyboard navigation of the gallery, and locks (a style is not in a text range). The open question "side panel, popover or modal" was answered in code with a popover at the caret; a mock-up review is still wanted.
- [ ] **E6.1 · Sheet model on the kernel**
	As a user, I want the demo's workbook (sheets, cells, layout, names, objects) on claudia-core.
	
	AC: commands, formulas, typed values, structure edits and names ported; the demo's relevant tests pass or are replaced with equal coverage.
	
	Use case: ALL · Decisions: D18
	
	Status evidence: well past the mini-port — sheets, typed cells, `SetCells`, `AddSheet`, `RemoveSheet`, `Structure` with exact inverses, `CellRegion`, `parse_input`, and a full formula engine (172 tests). **Not done:** named ranges (E6.5), objects and drawing, layout (row heights and column widths), and SQL (E4.9).
- [ ] **E6.3 · Grid in the frontend**
	As a user on any client, I want a grid that scrolls smoothly over huge sheets with the same interactions everywhere.
	
	AC: no element per cell, scrolling beyond the demo's cap, rows paged from the server which is the only calculator; selection, in-place editing and click-to-insert references, the same keyboard behaviour in every shell, an input method working in the cell editor; presence outlines and the calculating state drawn.
	
	Use case: ALL · Decisions: D2, D36, D42
	
	Status evidence: the virtualised grid is built with chunked paging (64×16), selection, in-place editing, copy and paste, presence outlines, and point-and-click references while typing a formula (`web/app/lib/pointing.ts`, 22 cases in `web/tests/pointing.test.ts`, the nine-case browser scenario `npm run e2e:pointing`; rebuilt and verified in the tree 2026-11-06 after PROC-03 found the first claim uncommitted). Also not done: the calculating state (needs E4.3), column resizing, an input-method test, and Ctrl+arrow beyond loaded cells. Accessibility is absent (UX-02), and the window query is linear in the sheet (PERF-01).
- [ ] **E6.4 · Numeric semantics**
	As a user, I want predictable numbers, so that models can be trusted.
	
	AC: a decision recorded on the demo's INT type and "division is always float" versus Excel's doubles; tests for edge cases such as `=9007199254740993`.
	
	Use case: FIN, SCI · Decisions: D12, D23
	
	Status evidence: the behaviour is implemented and tested — whole numbers exact to 2^53 then float, `/` always float, text never coerced (`="3"+2` is `#VALUE!`), TRUE/FALSE as 1/0 in arithmetic, sums through `math.fsum` so sparse iteration order cannot change a result, rounding via `Decimal(repr(x))`. **The decision is not recorded**, so this is code without a decision behind it; writing it into `decision-log.md` closes the story.
- [ ] **E6.7 · Copy, paste and Paste As**
	As a user, I want copy and paste with shifted references and a Paste As menu.
	
	AC: the demo's behaviour kept; Paste As options listed and tested; tab-separated clipboard interop.
	
	Use case: ALL · Decisions: D4
	
	Status evidence: tab-separated clipboard copy and paste are built (`lib/selection.ts`, with a 10,000-cell limit). **Not done:** shifting relative references on paste (`rewrite.shifted` exists in `claudia-computes` and is tested, but nothing calls it from the paste path) and the Paste As menu, which D74 puts in Edit.
- [ ] **E6.8 · Tools menu for computes**
	As a user, I want app-specific tools in the Tools menu.
	
	AC: re-roll random numbers, a Functions list, New Function, Track/History window access; everything where the manifest says.
	
	Use case: ALL · Decisions: D4, D25
	
	Status evidence: a Tools menu exists in the web app, but the items this story names do not: there is no RANDOM to re-roll, no Functions list, no New Function (E4.10), and no manifest to place them from (E5.1).
- [ ] **E7.1 · AI server**
	As an operator, I want a separate AI server hosting the model, so that all three apps share it.
	
	AC: an engine abstraction; an OpenVINO engine with a configurable device (GPU default); per-document fairness, cancellation and a visible queue position; the model loaded at start-up with readable errors.
	
	Use case: ALL · Decisions: D2, D13
	
	Status evidence: `claudia-ai` is built — `LanguageModel`/`ModelError`, `OpenVinoModel` using `openvino_genai.LLMPipeline`, `ModelRunner` (one worker thread, FIFO across documents, timeout from the start of generation, cancel and close stopping generation per token), and an `Agent` that builds the prompt and reads the answer. The CLI takes `--ai`, `--ai-device`, `--ai-max-tokens` and `--ai-timeout`, GPU is the default (D13), and a corrupt model folder gives a readable message. **Not done: it is not a separate server** — it is a package the doc server imports (E3.6). **Never run against a real model**: Hugging Face and the PyTorch index were blocked in the build sandbox, so the first run on a real machine is the real test. No visible queue position.
- [ ] **E7.3 · Engine adapters**
	As an operator, I want to choose OpenVINO, Ollama or Claude's API, so that I decide where the model runs.
	
	AC: an interface with tool calls and streaming; three adapters; remote models need explicit opt-in per server and a visible indicator in the UI.
	
	Use case: ALL · Decisions: D13, D32
	
	Status evidence: the interface exists (`LanguageModel.generate(messages, max_new_tokens, stop)`) with one adapter, OpenVINO, plus a `FakeModel` for tests. **Not done:** Ollama, Claude's API, streaming, real tool calls (the convention is a fenced `commands` block parsed from the text), and the opt-in and indicator that D32 requires before any document content leaves the server.
- [ ] **E7.5 · Document context for the model**
	As a user, I want the AI to see the relevant part of my document, so that its help is useful.
	
	AC: read tools (viewport, selection, names, recent history and help search); size limits; prompt-injection mitigations for cell contents.
	
	Use case: ALL · Decisions: D24
	
	Status evidence: `apps.workbook_context` gives the model how rows are counted, an example request, and the sheets as `id: name` (at most 50, whitespace collapsed so a sheet name cannot add lines to the prompt). **Cell contents are not shown to the model**, so the AI is of little use for questions about data — and there is no prompt injection from cells *yet*. There are no read tools and no observe-act loop. **Build the authorisation fix of SEC-10 before this story, not after:** this is the story that turns document content into model input, and the method allow-list is currently enforced in the model's output parser.
- [ ] **E8.3 · Server images**
	As an operator, I want container images and a compose file for each doc server and the AI server.
	
	AC: images and a compose file; documented ports, volumes and environment; health checks; the Python version matching the project's.
	
	Use case: PLATFORM · Decisions: D2
	
	Status evidence: a `Dockerfile`, `docker/entrypoint.sh` and `docker/healthcheck.py` exist, and the server has `/api/health` and a state folder. **Not done:** a compose file, documented volumes and environment, an image for the AI server, and anything published.
- [ ] **E8.4 · CI on three OSes**
	As a developer, I want tests to run on Linux, Windows and macOS, so that platform bugs appear early.
	
	AC: unit tests on all three; GTK smoke tests; the bundle test from E0.6.
	
	Use case: PLATFORM · Decisions: D22
	
	Status evidence: `.github/workflows/ci.yml` has a Python matrix over ubuntu, windows and macos running the gate, a web job, a Monday schedule and `workflow_dispatch`. **Two holes:** the gate silently skips the web checks in the Python job because nothing runs `npm install` there, and still reports "everything is clean" (PROC-02); and there is no bundle test and no GTK smoke test beyond the Linux client's own job. Whether the matrix has ever passed on Windows or macOS is not visible from the tree, and the Windows typesetting sandbox has never executed anywhere.
- [ ] **E9.1 · Text document model**
	As a writer, I want a document model of blocks and inline marks on the kernel.
	
	AC: commands for insert, delete, format and structure; Region for text ranges; the toy-model tests replaced by the real model.
	
	Use case: ALL · Decisions: D1, D17
	
	Status evidence: `TextModel` is real — paragraphs with stable ids never reused, named styles, authorship runs, suggestions as proposals, `TextCommand.follow` for moving a span through a command, `TextRange`, run arithmetic, state events (83 tests). **Not done: inline marks** (no bold, italic or underline), lists and tables; and the open decision of E9.10 — how a text command keeps the identity of moved or pasted runs — has to be settled here, before the editor grows.
- [ ] **E9.3 · Editor in the frontend**
	As a writer, I want a rich-text editor in the frontend, so that composes works the same in every client.
	
	AC: the editor library recorded after a spike; input methods and accessibility checked with E0.8; the same toolbar placement in every shell.
	
	Use case: ALL · Decisions: D42
	
	Status evidence: built as an own `contenteditable` (`TextEditor.vue`) where the browser never edits the page and only server events do — so no third-party editor was chosen and no spike was recorded. **Not done:** inline marks, windowing for long texts (the whole document is loaded through `blocks`), input methods beyond sending composed text at composition end, accessibility, and recovering text typed in the browser if the request fails.
- [ ] **E9.6 · Flow view and page view**
	As a writer, I want to write in a flow view and switch to a page view in the same window.
	
	AC: flow is the default and a switch in the main window changes to the page view and back, remembered per person; no separate print preview dialog or overlay; the page view shows page size, margins, headers and footers from the page style and says where breaks may differ; cursor, selection, presence and suggestions behave the same in both.
	
	Use case: ALL · Decisions: D61, D42
	
	Status evidence: both views exist with a View-menu switch, and there is no print dialog, which is the part D61 cared about. **The page view is approximate:** a sheet with margins, no real page breaks, no headers or footers, because there is no page style (E9.14) and no pagination decision (E9.4).
- [ ] **E9.7 · Styles first, with an invitation to name**
	As a writer, I want to mark text by purpose, so that every difference in how text looks has a name and a reason.
	
	AC: paragraph and character styles are the main way to format, through the shared dialog, with deviating creating a new style and no anonymous direct formatting; applying a style with no name brings a small non-modal invitation to name it that never blocks typing and can be dismissed; unnamed styles collect in a "to name" list; a style is a command in the log; changing a style changes every use at once.
	
	Use case: ALL · Decisions: D62, D73, D75, D15
	
	Status evidence: built for **paragraph styles** — seven built-ins (Body text, Title, Heading 1/2, Quote, Remark, Definition, all based on Body text), deviation by default with provisional names and a `to_name` flag, the invitation shown once per style, `next_style` deciding what Enter starts after a heading, and two-author conflict tests. **Not done: character styles**, the "to name" worklist as its own view (the dialog has a filter), and nagging limits beyond once per style per session.
- [ ] **E9.8 · Style list and cleaning up imported formatting**
	As a writer who opens a file full of direct formatting, I want Claudia to propose named styles from the formatting that repeats.
	
	AC: a list of all styles with use counts and the "to name" list, with rename, merge and delete following the E1.10 rules; on import, repeated direct formatting is grouped and each group offered as a proposed style with a suggested purpose-based name, nothing applied until confirmed, and one step undoing the whole clean-up; a report of formatting that could not be grouped.
	
	Use case: ALL · Decisions: D62, D69
	
	Status evidence: the list is built (Format ▸ "All styles…") with use counts, a "to name" filter and rename. **Not done:** merge and delete (which need the E1.10 delete rules), and the whole import clean-up, which needs E9.5.
- [ ] **E9.9 · AI edits as suggestions**
	As an author, I want changes the AI proposes to appear as suggestions I can accept or reject, while colleagues' edits appear immediately.
	
	AC: a suggestion is a proposal anchored to a text Region, not a change, shown inline and in the panel; accepting makes a normal command attributed to the accepter with the suggestion's author recorded, rejecting is logged, and a suggestion is marked outdated when its anchored text changes; **the AI has no direct write path into composes text**; people's edits are applied immediately; viewers see no suggestions unless the key domains allow it.
	
	Use case: ALL · Decisions: D63, D17, D47
	
	Status evidence: built — `suggest` (assistant only), `accept_suggestion`, `reject_suggestion`, proposals anchored to a region, acceptance recorded as the accepter's edit with `via=ai`, and `SuggestionList.vue` in the panel. **The "no direct write path" guarantee, fixed 2026-11-06 (SEC-10):** `replace_text` and `set_style` refuse the assistant, and `apply` — inherited from the core table, so it used to bypass both — now refuses `account.system` unconditionally, and is also outside the assistant's allow-list (`apps.MODEL_METHODS["composes"] = ("suggest",)`), checked at dispatch. Also open: undoing a reject reopens the suggestion (intended?), redacting a propose step before its accept may break replay, and the stand-in does not propose around other people's locks.
- [ ] **E9.10 · Authorship view**
	As an author or reviewer, I want to see which user each word came from.
	
	AC: a view mode colouring text by author (and alternatively by time) with a legend, the `ai` user appearing as itself; **derived by replaying the command log, with no extra authorship data stored**; text commands keep the identity of runs that are moved, split or pasted, with outside text attributed to the person who pasted it; accepted suggestions show the accepter and, on hover, the suggestion's author; viewers without history access see no authorship; opening the view on a 100-page document is measured.
	
	Use case: ALL · Decisions: D63, D15
	
	Status evidence: built as "Show who wrote what" shading with the `via` field for accepted suggestions. **It deviates from the acceptance criterion:** the runs are *model state* that replay rebuilds, not a view derived on demand, so authorship is stored after all. Same result today, different property — confirm or change it, because it constrains E9.1. Not done: colour by time, the viewer restriction (E2.4), and the performance measurement.
- [ ] **E9.11 · AI thinking aids in composes**
	As a writer, I want the AI to help me think about my text on request.
	
	AC: on request the AI checks spelling, word choice, complicated wording and language style for a selection or the document, answering as suggestions with a short reason each; later structure and flow, summaries and content proposals; a "play a sceptical reader" request; persona and skills per app; aids switchable off per document; running on the document's configured engine with the opt-in indicator for a remote engine.
	
	Use case: ALL · Decisions: D64, D24, D32
	
	Status evidence: a scripted stand-in (`standin_text.py`) does the first half — spelling, wordiness, intensifiers, double spaces and long sentences, answering `review`/`check` for the whole text or "this paragraph", end-to-end tested through the hub and assistant. **Not done:** a real model behind it, structure and flow, summaries, the sceptical reader (E12.4), the persona and skills files (E7.2), the per-document switch, and the remote-engine indicator.
- [ ] **E10.1 · Slide model**
	As a presenter, I want slides made of shapes, text and images on the kernel.
	
	AC: reuses the object layer of the demo (anchors, z-order, groups); commands and Regions for object sets.
	
	Use case: ALL · Decisions: D1, D17, D77, D79, D81, D83
	
	Status evidence: built but new, not a reuse of the demo's `drawing.py` — slides with text boxes and shapes, commands for add and remove slide, add, move, resize, edit and remove object, define and forget shape, regions and events (62 tests); a deck starts with `s1`, ids are random and never reused, and frames are whole numbers in a 1600×900 space. **Not done:** images (E10.8), groups, anchors, z-order commands (only the order of the stack exists) and slide reordering.
- [ ] **E10.6 · Object track changes and locks**
	As a collaborator, I want objects added, removed and edited by others recorded and visible, and to lock a shape by marking it.
	
	AC: added, removed and moved objects and edited text are commands with an author, shown in the panel and on the slide; marking a shape, text box or group locks it for others, shown by an outline and name tag, ending on deselect or idle; the `ai` user is bound by the same locks and its changes are suggestions shown as ghost objects.
	
	Use case: ALL · Decisions: D67, D17, D47, D63, D82
	
	Status evidence: built — selecting holds an object, others see a coloured outline and name tag, clicking a held object is refused, text editing locks the box, and the history lists added, moved, resized, edited and removed objects with the author. **Not done:** groups, the ghost objects for `ai` suggestions (there is no AI in creates at all, D85), and idle release — a lock lapses after 300 seconds on the server but the client does not renew it and does not say so.
- [ ] **E10.7 · Few shapes**
	As a presenter, I want a small, deliberate set of shapes, so that I make clear slides and not drawings.
	
	AC: a shape set chosen with the owner (for example rectangle, rounded rectangle, ellipse, line, arrow, bracket, callout), everything else an image or a diagram; shapes take their colours from the template, and a different colour needs a new named style; pptx/odp import maps unknown shapes to the nearest shape or an image and reports it.
	
	Use case: ALL · Decisions: D67, D78, D79
	
	Status evidence: three shapes exist as JSON in the built-in library — rectangle, circle, triangle. **The deliberate set is still the owner's decision** (rounded rectangle, line, arrow, bracket, callout?), and colours come from the built-in style `plain-shape` in code, not from a template (E10.4).
- [ ] **E10.13 · First-draft follow-ups**
	As the project owner, I want the known gaps of the first creates draft written down as work, so that none is forgotten.
	
	AC: each item below becomes its own story when it is picked up; this story closes when the list is empty.
	
	Open items, all still open at `54d1245`: others see a drag as it happens (an unlogged preview as presence, like E4.8); multiple selection and a group lock, copy and paste of objects, deleting several, reordering in the stack; slide thumbnails, slide reordering, duplicate and delete slide in the UI (the commands exist); text boxes that grow with their text or warn when text is clipped, and text alignment and size through a style choice; renewing the selection lock while the person works in the object, or telling her it lapsed; the history wording, where a combined step reads "Add shape" while others read "Added a …" (the `Batch` label is both label and summary); styles in the document instead of two in code (E1.10), until when a release that changes the built-in styles restyles old documents; whether `aspect` should be a flag plus a ratio; an AI participant for creates; and the two-browser end-to-end test in CI, which needs a runner with Chromium.
	
	Use case: ALL · Decisions: D77, D80, D82, D85
- [ ] **E11.1 · Monorepo layout and tooling**
	As a developer, I want the monorepo laid out and wired up.
	
	AC: a top-level layout with a package per app, the shells and the AI server; workspace tooling for Python and Nuxt with a single command to run all tests; CI with path filters so a change builds only what it touches; each app and the AI server still buildable and releasable on its own, with a versioning scheme.
	
	Use case: PLATFORM · Decisions: D10, D39
	
	Status evidence: a uv workspace with ten Python packages plus `clients/linux` outside it (D116) and `web/`; one command for the Python side (`uv run pytest`, `scripts/check_debt.py`). **Not done:** CI path filters (every job runs on every change), releasing packages one by one, and a `web/` that joins the single command — the gate shells out to npm and skips it when `node_modules` is missing (PROC-02). `uv.lock.rej` is committed at the root (CODE-07).
- [ ] **E11.4 · Quality gates and technical-debt check**
	As a developer, I want one command and a CI job that check style, types, unused code, tests, documentation and performance.
	
	AC: `scripts/check_debt.py` runs ruff, mypy, vulture, the tests, the Sphinx build with warnings as errors and the performance guards, exiting non-zero if any fail; GitHub Actions run it on Linux, Windows and macOS on every change and weekly; tests first and clean code written down in `CONTRIBUTING.md`.
	
	Use case: PLATFORM · Decisions: D39
	
	Status evidence: built and genuinely green on the Python side — ruff, mypy, vulture, ~1,321 tests, Sphinx with warnings as errors, two performance guard suites, and the Linux client's own checks. **Three holes:** it reports "everything is clean" while skipping checks, and has no `--ci` to forbid that (PROC-02); it does not run `ruff format --check`, which fails today (CODE-08); and it runs no dependency audit (SEC-08). Coverage is not measured at all (CODE-01).
- [ ] **E11.5 · Versioned and documented APIs**
	As a maintainer, I want every public API versioned, snapshotted and documented from the code.
	
	AC: `__all__` and `__version__` per package, semantic versioning, a CHANGELOG per package, and a snapshot of names and signatures that fails the build on any change until version, changelog and snapshot are updated together; every public class, function and method has a docstring, checked by a test, with a Sphinx site generated from the code whose build fails on a broken reference; the network protocol has its own version and a documentation page.
	
	Use case: PLATFORM · Decisions: D21
	
	Status evidence: built and working — API snapshots under `tests/api/`, per-package changelogs, `PROTOCOL_VERSION` served at `/api/protocol`, and a Sphinx build with warnings as errors. `claudia-creates`, `claudia-container`, `claudia-fonts` and `claudia-typeset` have joined the snapshot rule. **Not done:** `claudia-computes` and `claudia-composes` are still exempt although both are now real products with large APIs, and the documentation site is not published anywhere.
- [ ] **E11.6 · Regular debt review**
	As the project owner, I want a recurring look at unused code, slow code and other debt.
	
	AC: the weekly CI run reports; a review of its output and of new `vulture_whitelist.py` entries at the end of each epic; findings become stories.
	
	Use case: PLATFORM · Decisions: D39
	
	Status evidence: the weekly schedule exists in CI and `vulture_whitelist.py` carries reasons per entry. The review itself is this QA round, which found that the mechanism works for code but not for claims: `bugtracker.md` PROC-03 records work described as delivered that is in no commit, and nothing in the gate would have caught it.
- [ ] **E13.1 · Help topics and their format**
	As a user, I want help written as short "how do I…" topics with a worked example each.
	
	AC: a topic has an id, a title phrased as a task, the apps it applies to, a language, tags, a short body of steps, **at least one worked example**, links to related topics and links to what it explains; the authoring format and rendering decided with E0.4; size rules so a small local model can read a topic whole, and an author guide; topics versioned with the thing they describe and flagged stale when the subject changes; no executable content.
	
	Use case: ALL · Decisions: D76, D30, D31, D99
	
	Status evidence: one topic exists as a **draft shape** — `claudia_typeset/help/configure-latex.md` (id `typeset.configure-latex`), Markdown with simple front matter, with tests checking the id, a title phrased as a question, the metadata, the worked example, that it names both settings and the pitfalls, and a size cap so a small model can read it whole. **The format itself is undecided** and the file is to be converted once E0.4 settles the renderer.
- [ ] **E13.2 · Extensions must register their help**
	As a function or macro author, I want to register a tooltip, a help topic and a tested example together with my extension.
	
	AC: every UserFunction provides `get_tooltip` and `get_help`, registered when the function loads, with a function missing them refused at load with a readable message; the same contract for every extension point in composes and creates, and **no extension point opened there without it**; one small versioned interface in `claudia-core`; at load the help is rendered once and its examples are run as tests, with a failure shown to the admin; help of a function is available whenever the server has it loaded; help text from extensions is untrusted data for the AI.
	
	Use case: ALL · Decisions: D76, D29, D30, D38
	
	Status evidence: half the contract is built, in the right spirit: `functions/base.py` makes a description and at least one `Example` mandatory, and `check_examples` runs the examples in the tests. **Not done:** `get_tooltip` and `get_help` (E4.6), the registration into a help system that does not exist (E13.3), the interface in `claudia-core`, and the contract for composes and creates, whose macro API is still open (D29).


## testing



## done

- [x] **E1.1 · DocumentModel interface**
	As an app developer, I want a small interface (apply command, return inverse, describe regions, serialize state, schema version) that each app implements, so that composes, computes and creates share one kernel.
	
	AC: extracted from the demo so the kernel contains no spreadsheet code; a toy model runs on the kernel in tests; the kernel does no I/O.
	
	Use case: PLATFORM · Decisions: D10, D15, D37
	
	Status evidence: `model.py`, `commands.py`, `context.py`, `document.py`; a toy `ListModel` in `testing.py`; a purity test proves no I/O and no app words in the kernel. All four apps implement it.
- [x] **E1.2 · Command log as source of truth**
	As an owner, I want the saved document to be its command log, so that the history is complete and any past state can be rebuilt.
	
	AC: replaying the log from empty gives the identical state (randomized test); revision identifiers can branch; a snapshot is a cache that can be deleted and rebuilt.
	
	Use case: ALL · Decisions: D15, D45
	
	Status evidence: `log.py`, `replay.py`, `revision.py`, `Document.open/materialize/snapshot`. Randomized replay equals live state including undo stacks; snapshots are ignored if foreign or stale. The first debt run found `since()` and undo cost growing with the whole log; both now cost only the entries involved, with scaling guards that fail if it regresses.
- [x] **E1.3 · Command schema versioning**
	As a maintainer, I want every command to carry a schema version with upcasters, so that old documents open forever.
	
	AC: fixture logs of earlier schema versions replay after a version bump; plugin extensions use the same mechanism; a log from a newer schema is refused with a clear message.
	
	Use case: PLATFORM · Decisions: D21
	
	Status evidence: envelope `{k, s, d}` with a registry and upcasters, tested with a fixture log of version 1 (upcast) and version 3 (refused). Thin but complete for what exists; the shape format (D78) and the CSS allow-list (D75) are versioned the same way.
- [x] **E1.4 · Per-author undo**
	As an editor, I want undo and redo of my own steps only, so that I never revert a colleague's work.
	
	AC: undo is a new command; randomized undo/redo/replay tests pass; undo is refused when it would touch a region someone else holds, and when a colleague wrote the same cell after my step.
	
	Use case: ALL · Decisions: D15, D17, D46
	
	Status evidence: `history.py` plus `Command.shifted_by`, which moves a stored inverse through everything that ran since; `None` means a colleague changed it and the undo is refused with `UndoConflict`, consuming nothing. Undo stacks are rebuilt from the log, so reopening a document restores everybody's stacks. Known gap carried to E9.3: there is no undo grouping, so typing is one step per word.
- [x] **E1.5 · Region abstraction**
	As an app developer, I want one Region type with an overlap test and a way to move with edits, so that presence, locks and AI edits are written once.
	
	AC: a cell range implementation moves with row and column inserts and deletes; the interface works for a text range and an object set in tests; presence and locks use only the interface.
	
	Use case: ALL · Decisions: D11, D17
	
	Status evidence: `region.py` and `presence.py` in the kernel, with `CellRegion` (computes), `TextRange` (composes), `ObjectSet` (creates) and `Interval` (toy). Locks are enforced by `execute` for everybody including `ai` (D47).
- [x] **E1.6 · Message classes**
	As a developer, I want three message classes (durable commands, chat records, ephemeral messages), so that retention and visibility differ correctly.
	
	AC: presence, preview values and typing indicators are never stored; chat lives in the chat key domain; commands live in the log; a test shows an ephemeral message never reaches disk.
	
	Use case: ALL · Decisions: D32, D34, D37
	
	Status evidence: `messages.py`, `store.py`, `Document.publish/post_chat`. The store interface has no method for ephemeral messages at all, which is the strongest form of the guarantee. Chat is not a command; each record keeps the revision it was written at.
- [x] **E1.7 · Checkpoints**
	As an editor, I want File ▸ Save to create a named checkpoint, so that I can mark and return to a state.
	
	AC: a checkpoint is label, author and revision; listing; **restoring forks**, so the document continues on a new line and the old future stays on a hidden side line until an owner discards it, with `switch_to` as the way back; an unchanged document yields no empty checkpoint.
	
	Use case: ALL · Decisions: D5, D15, D45, D48
	
	Status evidence: `save_checkpoint`, `restore_checkpoint`, `switch_to`, `lines`, `discard_side_history`, and `core.Restore`/`core.Switch` log entries. Edits made against a line that is no longer active are refused (`StaleEdit`, D49). The kernel half is complete; exposing it in a live session is E3.7, now also done.
- [x] **E3.7 · Restore in a live session (consent flow)**
	As an editor or owner, I want to propose going back to a checkpoint while others are working, and have it happen only if everybody editing agrees.

	AC: the rule of D51 and the details of D52 (who is asked, how a vote ends, people coming and going, work during the vote, switching back to a hidden line, the notice for users who were away); protocol methods to propose, withdraw and answer, and events for the open proposal, each answer and its end; permission checks; everybody moves to the new line on restore; the banner is a frontend component with proposer, checkpoint, who has agreed and a countdown; tests with three clients covering a decline, an expiry, a user leaving mid-vote, an editor joining mid-vote, a sole editor, a viewer, the `ai` user and a second proposal while one is open.

	Use case: ALL · Decisions: D48, D49, D51, D52, D149, D150 · The consent machinery (`RestoreCoordinator`, entirely in-memory, lost with the document like presence and locks) is a new module in `claudia-server`, not the kernel (D150); every new wire method sits on the shared `core_methods` table, so composes and creates get it for free the same way they already share history and chat.

	Status evidence: `claudia_server.restore.RestoreCoordinator` plus seven new wire methods (`propose_restore`, `propose_switch`, `answer_restore`, `withdraw_restore`, `discard_side_history`, `restore_policy`, `set_restore_policy`) and two events (`restore_proposed`, `restore_resolved`); a sole owner/editor is applied at once, otherwise everybody connected as owner or editor must agree, one decline ends it, and the per-document `consensus`/`veto` policy decides what silence at the deadline means; `joined`/`left`/`sweep` handle a vote resolving while people come and go; a returning person's `welcome` carries a one-time `returned` notice of what happened to the line they were left on. 27 isolated `RestoreCoordinator` tests plus 36 hub-level integration tests (`test_server_restore.py`, `test_server_restore_live.py`). The frontend (`BaseSession.proposeRestore`/`proposeSwitch`/`answerRestore`/`withdrawRestore`/`setRestorePolicy`, `SidePanel.vue`'s consent banner and a restore button on every checkpoint mark) is built and shared by every app through the same session/panel layer already used for history and chat. **Not done:** no countdown — the deadline exists on the wire (`expires_at`) but nothing counts it down for the person.
- [x] **E3.8 · Line picker (first version)**
	As a user whose work is on a line that is now hidden, I want to see the lines of the document and pick one to go back to.

	AC: a list of lines (who restored, when, from which checkpoint, authors and number of commands per line, visible according to the key domains); a read-only preview before proposing; choosing a line proposes `switch_to` under the same consent flow; the notice for returning users links to the picker.

	Use case: ALL · Decisions: D48, D51, D52, D149 · Needed E3.7, done together with it. The read-only preview did need a kernel feature, agreed with the owner: `Document.peek_line(line)` (D149), a thin wrapper around the existing `materialize`.

	Status evidence: the kernel's `peek_line` (`test_peek_line.py`, 7 tests) and its wire method of the same name; `SidePanel.vue`'s "Lines" section lists every line with the active one marked, a "peek" button that shows the line's raw state, and a "suggest switching here" button that calls `proposeSwitch` under the same consent flow as a restore; owners also get a "forget every hidden line" button (`discard_side_history`, refused while a suggestion is open, so it can never discard what a proposal is aimed at). **First version, deliberately short of the AC:** a line shows only its name, head and fork point, not who restored it, when, its authors or its number of commands; the peek is the line's raw JSON state, not a rendered, per-app live preview; the returning-person notice is a plain sentence, not a link that opens the picker.
- [x] **E3.1 · Hub, connection and auth**
	As a developer, I want the demo's hub, connection and protocol machinery with document-local authentication, so that all three servers use one tested base.
	
	AC: name and password against the document's users; one WebSocket per person and document with the `hello` handshake carrying credentials; wrong password, unknown name and missing document give the same answer; a protocol table that an app extends, with error codes including `locked`, `conflict` and `stale`; **an edit carries the revision of the view it was made against and is refused with `stale` if the document has moved**; kernel events reach only the right people; limits and clean handling of slow or dead clients.
	
	Use case: PLATFORM · Decisions: D10, D35, D47, D49, D50
	
	Status evidence: all of it is built, across `claudia-server` (hub, protocol, auth, app, certificates, redirect port) and `claudia-client` (`TlsPolicy`), with the kernel kept free of network code. 416 tests. The protocol is served at `/api/protocol` with `PROTOCOL_VERSION` 1 and described in `docs/server.md`. Three method tables now extend it (core, computes, composes, creates). The known gaps each have their own story and are listed there: viewers receive everything (E2.4), no rate limiting (E2.7), locks are per user name rather than per connection.
- [x] **E4.1 · Incremental recalculation**
	As a user, I want an edit to recalculate only what depends on it, so that large sheets stay responsive.
	
	AC: a persistent dependency graph; dirty propagation in topological order; a randomized equivalence test against full recalculation; measured against the E0.7 baseline.
	
	Use case: ALL · Decisions: D37
	
	Status evidence: built in `calc.py` and measured. The closure is found level by level; the order is found while calculating by following a formula's waiting precedents depth-first with an explicit stack, so a 20k-deep chain is fine; a formula met again while waiting for itself makes every cell of the cycle `#CIRC!`; nothing is calculated while commands apply, so a batch of changes settles once. One edit in a 50k-row workbook with range readers costs about 0.25 ms. Remaining work is in its own stories: no early cutoff (a formula whose result did not change still dirties its dependents), and structure edits are not incremental (PERF-07).
- [x] **E4.2 · Range dependency index**
	As a user, I want range references (`SUM(A1:A100000)`) to be cheap, so that data sheets work.
	
	AC: an interval or bucket index for ranges; no quadratic scan; cycle detection kept; spilled results participate.
	
	Use case: DATA · Decisions: D37
	
	Status evidence: ranges are filed by blocks of 256 rows per column, with a list of its own for a range longer than 16 blocks and for ranges wider than 64 columns. Asking "who reads any of these cells?" for a whole batch costs one bisection per interval however many cells there are, so pasting ten thousand cells does not cost ten thousand scans — measured as 0.25 ms against 16.7 ms before the index. Spill does not exist yet (E4.6), so that clause is vacuous rather than met.
- [x] **E4.7 · Lookup and reference functions in the core**
	As a user, I want VLOOKUP, XLOOKUP, INDEX, MATCH, OFFSET, INDIRECT, ROW and COLUMN to be fast, so that real models work.
	
	AC: implemented in the core with indexes; behaviour tests; performance targets from E0.7; Excel-exactness not required.
	
	Use case: FIN, DATA · Decisions: D23
	
	Status evidence: all of them are built as core forms in `formula/forms/` with lazy arguments, `Range` references and per-column lookup indexes (capped), alongside IF, IFS, IFERROR, IFNA, CHOOSE, SWITCH, the IS\* family, ROWS, COLUMNS, XMATCH and HLOOKUP. Functions that read cells their text does not name (OFFSET, INDIRECT) are marked dynamic: always rechecked, with where they actually looked recorded, so they wait for the formulas they read and are found again when those cells change.
- [x] **E9.2 · Cursor and ± n words lock**
	As a collaborator, I want to see colleagues' cursors and have a zone around mine protected, so that we do not type over each other.
	
	AC: a zone of ± n words (configurable); the word rule defined; release on idle; boundary cases tested.
	
	Use case: ALL · Decisions: D11, D17
	
	Status evidence: built as the server methods `look` and `hold` over `TextRange`, enforced by the kernel for everybody including `ai` (D47), with the client drawing carets and ± 3-word zones and showing refusals. The remaining nuance is shared with E5.9: locks are per user name, not per connection.
- [x] **E10.12 · Shape library and shape format**
	As a user, I want shapes to be small JSON files in a folder that I can add to, so that the collection is extensible without changing the program.
	
	AC: format version 1 with `format`, `id`, `name`, `path` (absolute `M`, `L`, `C`, `A`, `Z` in a 100×100 box with a strict grammar) and optional `aspect` and `text_area`, with invalid files skipped and listed at start-up naming the offending part; a library is a folder, the built-in one always loaded and `--shapes DIR` adding more, a later folder replacing a shape of the same id; **a document embeds the definitions of the shapes it uses** and opens without the library; the insert bar lists the library's shapes by name.
	
	Use case: ALL · Decisions: D78, D79
	
	Status evidence: all of it is built and tested with fixture files. Known follow-ups, which are E10.13 rather than this story: no way to add a shape from the web app (the folder is on the server), no shape categories, and no shapes with several paths or fill rules.
- [x] **E6.2 · Virtualised grid in GTK — dropped**
	Superseded by E6.3. A native GTK grid is no longer built; the frontend has one grid that every shell shows (D42).
	
	Use case: DATA · Decisions: D42 · Kept for traceability only; no work remains.




%% kanban:settings
```
{"kanban-plugin":"board","list-collapse":[false,false,false,false]}
```
%%