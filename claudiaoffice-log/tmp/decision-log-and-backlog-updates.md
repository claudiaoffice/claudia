# Decision log and backlog updates for the i18n groundwork slice

Three edits, all in `claudiaoffice-log/`. None of this is in the code patch (`i18n-groundwork.patch`) — apply by hand
alongside it.

## 1. `claudiaoffice-log/decision-log.md` — update D31's row

**Find** (line 99 as of commit `d3df64a`):

```
| D31 | English first, **internationalization built in** from the start: every menu item and text is translatable. | 2026-11-01 | Proposal: gettext `.po` as the single source. **Not started:** no catalogue exists anywhere. |
```

**Replace with:**

```
| D31 | English first, **internationalization built in** from the start: every menu item and text is translatable. | 2026-11-01 | gettext `.po` as the single source, confirmed (over ICU/vue-i18n) — see D141 for the groundwork now built. |
```

## 2. `claudiaoffice-log/decision-log.md` — add a new round section

Insert immediately **before** the `## Open design questions` heading (after the "Additive xlsx/docx/pptx
extensions (twenty-second round)" section — the file already has two sections labelled "twenty-first round" and
two labelled "twenty-second round" from a prior parallel-merge collision, pre-existing and unrelated to this patch;
this new section is deliberately "twenty-third" to not add to it):

```markdown
## Internationalization groundwork (twenty-third round)

The groundwork for E5.7 (D31), not the full epic: no interface string has moved into a catalog yet, by design — the
plumbing is proven first, with an (almost) empty catalog, so moving real strings later is mechanical.

| ID | Decision | Date | Notes |
|---|---|---|---|
| D141 | **gettext `.po` is the single source of translations (confirmed over ICU/vue-i18n, D31): the web client's JSON catalog is derived from it (`scripts/po_to_json.py`), never maintained separately.** A locale is always a client-side setting (no server-side account profile exists to keep it on, D35): detected from the OS/browser by default, with a `Config` override to come later (D31, not built — no screen design exists yet for it, per the project's own "screens before code" rule). This round built: the server protocol's `hello`/`welcome` carry the connection's own `locale` (`PROTOCOL_VERSION` 2, `Context.locale`, nothing reads it yet); `KernelError` subclasses gained a stable `code: ClassVar[str]` independent of their English message (`claudia-core` stays dependency-free and catalog-agnostic — `test_purity.py`); the GTK client got a `gettext` skeleton (`clients/linux/src/claudia_shell_gtk/i18n.py`: locale detection and negotiation, `install_translation` binding `_` process-wide) with no strings moved yet; the web client got a matching loader skeleton (`web/app/lib/locale.ts`, `i18n.ts`: `loadCatalog`, `createTranslator`) and its two naive `toLocaleTimeString`/`toLocaleDateString` calls (`web/app/lib/people.ts`) now take the app's own negotiated locale instead of silently following the browser's; `scripts/extract_i18n.py` collects every `_("...")`/`t("...")` call into one shared `po/claudia.pot`, gated in CI (`check_debt.py`'s new "i18n extraction" check) so the template can never go stale; `scripts/make_pseudolocale.py` proves the pipeline end to end with a mechanically "translated," padded, accented `xx` pseudo-locale (not a real BCP-47 tag any browser would send) — currently empty, since nothing is extracted yet. | 2026-11-07 | Help-text translation (tooltips/`getHelptext()` vs. longer topic files) was discussed in the same round but not decided or built: short strings would go through the same `.po`; longer topics would likely need their own per-language files with staleness tracking against the English source — left for E13.8/D76, both still open. Built across all three apps structurally, with no per-app code: the server's `hello`/`Context`/`Connection` layer is shared by every app's `MethodTable`; the Linux shell wraps the same web app for all three. |
```

## 3. `claudiaoffice-log/backlog.md` — update E5.7's status line

**Find** (around line 136):

```
	Status evidence: no gettext, no `.po`, no babel anywhere in `packages/*/src`, `web/app` or `clients/linux/src`.
```

**Replace with:**

```
	Status evidence: groundwork built (D141) — kernel error codes, the protocol's `locale` field, a GTK gettext
	skeleton and a web loader skeleton, `po/claudia.pot` extraction gated in CI, a pseudo-locale proving the
	pipeline. Still open: no real string has moved off plain English into `_()`/`t()` anywhere; no Config-menu
	override (no screen design yet); numbers/dates typed by a user are not locale-parsed before a command is made.
```

The checkbox stays `[ ]` — the epic is not done; this is the slice the owner asked for first.

---

**Separately, FYI, not fixed by this patch:** `claudiaoffice-log/decision-log.md` already has `D135` allocated
twice (the row-height/column-width round and the xlsx/docx/pptx-io round both claim it, and both are also
mislabelled "twenty-second round" while an unrelated round sits at "twenty-first round" twice) —
`tests/test_decision_log.py::test_decision_log_never_allocates_a_number_twice` fails on current `main` (`d3df64a`)
over this, independent of anything in this patch. Likewise `packages/claudia-server/CHANGELOG.md` has two
`## [0.9.0]` headers with `## [0.10.0]` sandwiched between them. Both look like the same class of parallel-PR
collision D133 was written to catch for decision numbers; worth a cleanup pass, but out of scope here.
