---
id: D148
title: "gettext `.po` is the single source of translations (confirmed over ICU/vue-i18n, D31): the web client's JSON catalog is derived from it…"
status: current
applies-to: all
date: 2026-11-07
round: "Internationalization groundwork (twenty-fifth round)"
supersedes: []
superseded-by: []
---

# D148 · gettext `.po` is the single source of translations (confirmed over ICU/vue-i18n, D31): the web client's JSON catalog is derived from it…

**gettext `.po` is the single source of translations (confirmed over ICU/vue-i18n, D31): the web client's JSON catalog is derived from it (`scripts/po_to_json.py`), never maintained separately.** A locale is always a client-side setting (no server-side account profile exists to keep it on, D35): detected from the OS/browser by default, with a `Config` override to come later (D31, not built — no screen design exists yet for it, per the project's own "screens before code" rule). This round built: the server protocol's `hello`/`welcome` carry the connection's own `locale` (`PROTOCOL_VERSION` 2, `Context.locale`, nothing reads it yet); `KernelError` subclasses gained a stable `code: ClassVar[str]` independent of their English message (`claudia-core` stays dependency-free and catalog-agnostic — `test_purity.py`); the GTK client got a `gettext` skeleton (`clients/linux/src/claudia_shell_gtk/i18n.py`: locale detection and negotiation, `install_translation` binding `_` process-wide) with no strings moved yet; the web client got a matching loader skeleton (`web/app/lib/locale.ts`, `i18n.ts`: `loadCatalog`, `createTranslator`) and its two naive `toLocaleTimeString`/`toLocaleDateString` calls (`web/app/lib/people.ts`) now take the app's own negotiated locale instead of silently following the browser's; `scripts/extract_i18n.py` collects every `_("...")`/`t("...")` call into one shared `po/claudia.pot`, gated in CI (`check_debt.py`'s new "i18n extraction" check) so the template can never go stale; `scripts/make_pseudolocale.py` proves the pipeline end to end with a mechanically "translated," padded, accented `xx` pseudo-locale (not a real BCP-47 tag any browser would send) — currently empty, since nothing is extracted yet.

**Notes.** Help-text translation (tooltips/`getHelptext()` vs. longer topic files) was discussed in the same round but not decided or built: short strings would go through the same `.po`; longer topics would likely need their own per-language files with staleness tracking against the English source — left for E13.8/D76, both still open. Built across all three apps structurally, with no per-app code: the server's `hello`/`Context`/`Connection` layer is shared by every app's `MethodTable`; the Linux shell wraps the same web app for all three.
