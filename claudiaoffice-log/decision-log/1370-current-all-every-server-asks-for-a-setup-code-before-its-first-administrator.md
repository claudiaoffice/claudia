---
id: D1370
title: "Every server asks for a setup code before anyone becomes its first administrator, whatever address it listens on"
status: current
applies-to: all
date: 2026-11-20
round: "SEC-12: the first administrator needs a setup code (branch sec-12-setup-code)"
supersedes: []
superseded-by: []
---

# D1370 · Every server asks for a setup code before anyone becomes its first administrator, whatever address it listens on

**Decided 2026-11-20** by the owner (variant B of the SEC-12 mock-up, `notes/mockups/sec12-first-administrator-setup-code.svg`).

**Why.** Until now `POST /api/admin/setup` needed only a name and a password while the server had no administrator
(SEC-12, P1). On an exposed server the first visitor won; an administrator can remove the access secret, point the AI
at any folder and name any program as `xelatex` (SEC-16), so winning meant running programs as the server's account.
Asking for the code only when `--host` is not a loopback address (variant A) leaves two holes: a server on 127.0.0.1
behind a proxy on the same machine, and every other account of a shared computer (a school's, a terminal server),
which reaches 127.0.0.1 too.

**Decision.** `setup` needs the server's setup code (D1371) on every server, loopback included. Who can read the
server's log or its state folder runs the server; that is what the code proves. The desktop apps hand the code over
themselves (D1373), so a person on her own computer types nothing.

**The code alone is enough**, also on a server with an access secret: whoever reads the log already runs the server,
and a second secret field would only make the form heavier (owner, 2026-11-20). The access secret keeps its own job:
making documents and reading their list (UX-61).

Supersedes the recommendation in SEC-12's section of the tracker (code only on exposed servers, and code plus secret).
D176 stays: the page is offered whenever nobody has ever been named; only the form gains its field.
