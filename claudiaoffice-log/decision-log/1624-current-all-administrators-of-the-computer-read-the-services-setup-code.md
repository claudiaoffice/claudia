---
id: D1624
title: "The computer's administrators name the service's first administrator: their apps read its setup code, anyone else's says to ask one"
status: current
applies-to: all
date: 2026-11-25
round: "E8.5 macOS installer, part 2: Shared on this computer (branch `mac-installer`); decided in the grilling of 2026-11-25 (Q17)"
supersedes: []
superseded-by: []
---

# D1624 · The computer's administrators name the service's first administrator: their apps read its setup code, anyone else's says to ask one

**While the computer's service (D1622) has no administrator, its setup code (D1370) is in its state folder, which only the
computer's administrators and the service may read: the macOS package gives the `admin` group read on it, the Windows
installer takes the inherited access of `Users` off `%ProgramData%\Claudia\state` and keeps `SYSTEM`, `Administrators`
and `LocalService`. An app that may read the code sends it with the service's page in `welcome` (`setup_code`), as for her
own server (D1373); an app that may not sends `ask_administrator`, and the setup page's code field says "Only an
administrator of this computer can name this server's first administrator. Ask one."** The field stays: an administrator
may tell her the code.

**Why.** Q17 of the grilling: the service is the computer's, so the people who look after the computer name its first
administrator; everyone else could otherwise make herself the administrator of everybody's shared documents. A person
who may not read the file is told whom to ask instead of where a file is that she cannot open.

**How.** `clients/neutralino/src/shared-service.ts` reads the code anew at every `show` (`setupCodeAccess` in
`private-server.ts`: the code, none, or "may not" when reading it is refused; the file is read, since on Windows Node's
`access()` ignores ACLs); `core.ts` turns it into `setupCode` or `askAdministrator`; contract v1 gets
the optional `welcome.ask_administrator` (`clients/contract/shell-contract.v1.schema.json`); the page keeps it for the tab
(`web/app/lib/setup-code.ts`) and `FirstAdminSetup.vue` shows the sentence.

**Alternatives.** The service's code readable by everyone of the computer: anyone becomes the shared place's administrator.
A setup by the installer (asking for the first administrator while installing): the owner chose the same setup page as
for every server.

**Known limit (Windows).** With User Account Control on, an administrator's apps run without the rights of the
`Administrators` group, so they cannot read the code either and say to ask an administrator; she reads
`%ProgramData%\Claudia\state\admin\setup-code` herself (Explorer asks for her administrator's consent) and types it.
UX-95; macOS has no such split. That the folder was open to every account before is SEC-29 (fixed by this decision).
