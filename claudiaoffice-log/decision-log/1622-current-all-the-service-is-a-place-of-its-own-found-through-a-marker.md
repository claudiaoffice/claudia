---
id: D1622
title: "The service is a place of its own, \"Shared on this computer\", found through a marker its installer writes"
status: current
applies-to: all
date: 2026-11-25
round: "E8.5 macOS installer (branch `mac-installer`); decided in the grilling of 2026-11-25, built in part 2"
supersedes: []
superseded-by: []
---

# D1622 · The service is a place of its own, "Shared on this computer", found through a marker its installer writes

**A claudia service on a computer (macOS and Windows; the Linux package has none) is a shared server on 8765 (D1621), never
a person's own (D1620): every person's apps list it after her private place as "Shared on this computer" (D1623) and
open it like any server. Its installer writes a marker, `service.json` (`{"origin": "http://127.0.0.1:8765", "state":
"<its state folder>"}`, in `/Library/Application Support/Claudia` on a Mac, `%ProgramData%\Claudia` on Windows), and
removes it with the service; the apps read it at start.** New documents go to her private place unless she picks the shared
one. Every person with an account on the computer may use it (no access secret by default, its administrator may set one);
it listens on this computer only. The computer's administrators can name its first administrator (D1624).

**Why.** The grilling of 2026-11-25 (Q13, Q16, Q18): the owner was surprised that the service simply *was* every person's
server ("What happens if there is a server service installed AND some user on the machine installs claudia…?"), and chose a
person's own server for every person, the service a place beside it.

**Changes D743**: its "the apps use the service's documents" no longer holds; the service stays as D743 describes it
otherwise (on 8765, loopback, its own account, off by default).

**Alternatives.** Finding the service by probing 8765: `./start.sh` would show up as the computer's shared place. People
adding it by hand (`127.0.0.1:8765`): the owner chose the automatic listing.

**Built** (2026-11-25, E8.5 part 2): `clients/neutralino/src/shared-service.ts` reads the marker
(`HostPlatform.sharedServiceFile`) and accepts only a loopback origin and an absolute state folder; `servers.ts` `forPage`
lists it after her private place (`shared: true` in contract v1's server entry); a name a person gives it is remembered
under its origin, its default name never, so it does not outlive the service. The Windows installer writes and removes
the marker (`packaging/windows/claudia.iss`); the macOS package does with part 3.
