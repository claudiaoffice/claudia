# Review of `server/administrators.feature` (draft of 2026-11-20, SEC-12)

How to answer: for each question, "ok" accepts my proposal; anything else replaces it. When all are answered I move the
answers into the feature file (and the decision log) and delete this file.

Decisions: D1370–D1376. Mock-up: `notes/mockups/sec12-first-administrator-setup-code.svg`; architecture:
`notes/mockups/sec12-architecture.svg`. No step code is written yet: every browser scenario skips until it is, and the
`@unit:` ones name the test that will check them.

**How they run.** The browser scenarios need servers the harness does not start yet: one with no administrator, one
behind a proxy, one started with extra options, and a restart. The step code gets a fixture that starts such a server
with its own state folder and reads its log, as the self-starting scripts do (`OWN_SERVER`). "A desktop app hands the
page a code" is simulated in the browser by calling the page's shell bridge (`window.__claudiaShell.receive`), which is
how the GTK shell talks to it; the shells' own part is checked by their unit tests.

| Q | Question | Proposal |
|---|---|---|
| 1 | A server started by hand on 127.0.0.1 keeps its optional wording ("isn't required … Skip for now"), with the code field above the name. Is the field on an optional page all right, or should the page say why it asks? | The hint under the field is enough: "In the server's log where it started, or in admin/setup-code in its state folder." |
| 2 | How many wrong codes before the server makes a person wait? | The same as the sign-in (D1266): three free tries per address, then a growing wait of at most 30 s. The check of a code from a link counts as a try. |
| 3 | The password file of `--admin`: what is the password? | Its first line, without the line end. An empty file, or a password the rules refuse, stops the server with a sentence, rather than starting it with no administrator and no hint. |
| 4 | The administrators moved aside by a reset (`admins-before-reset-<time>.json`) stay until someone deletes them. Should the server tidy them up? | No: they are small, and they are the only way back from a mistaken reset. |
| 5 | The reset note is shown to every administrator until one of them dismisses it. Also in the start banner at every later start? | No: the banner says it once, at the start that reset. |
| 6 | The demo on Scaleway starts afresh on every cold start, so it makes a new code each time until `CLAUDIA_ADMIN` and `CLAUDIA_ADMIN_PASSWORD` are set as secret variables there. | You set the two variables in Scaleway once the branch is deployed; until then the code is in the container's log. |
| 7 | Keys and menus: this adds a form field, a link and a Dismiss button, and no menu entry. | Nothing for the menus workbook; Dismiss is reached with Tab like the other buttons of the page. |
| 8 | BITV: the field is labelled "Setup code", says where to find the code (`aria-describedby`), takes `autocomplete="one-time-code"`, and its errors are announced (`role="alert"`). The check mark of a code from a link has its words next to it. Anything else? | No divergence from WCAG 2.1 AA expected; the screen-reader run is still not possible here. |
