---
id: D1267
title: "Password hashing targets 0.75 seconds, calibrated on the server's own hardware"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1267 · Password hashing targets 0.75 seconds, calibrated on the server's own hardware

**Decided by the owner 2026-11-19 ("let's put the KDF cost at 0.75 sec and see what happens"). Not built.** It settles the
open point of D109, whose target was about half a second and whose measured default (3 passes, 64 MiB, 4 lanes) takes
0.09 to 0.4 seconds.

- **Target.** One login takes about 0.75 seconds on the machine the server runs on. The server measures it when it starts
  and when the setting changes, and gives new documents the parameters it found. Existing documents keep theirs.
- **Floor and ceiling.** Never weaker than today's default. The memory per hash has a ceiling (default 256 MiB), so a small
  server such as a NAS does not run out of memory; what the memory ceiling cannot buy is bought with more passes (up to the
  limit the container reads, D104).
- **A server setting.** *Server settings ▸ Security*: the time one login may take (0.25 to 2 seconds, default 0.75), the
  memory ceiling, what the server measured, and a "Measure again" button. It says plainly that it applies to new documents.
- **The same cost for decoys.** The hash made for an unknown document (SEC-04) uses the server's current parameters, so a
  document and a missing document still take the same time.
- **Throughput.** At this cost the server hashes about one to two logins a second, which is why the waits of D1266 come
  with it. Whether single-lane hashing may run in parallel (the OpenSSL deadlock was with several lanes) is measured first
  (the architecture note names the check); if it holds, the cap can be raised without lowering the cost.
- **Passwords.** The rules of D109 do not change here. Their weak point, 8 characters, stays on the owner's list.

**Notes.** Correction to `KdfParams`: its docstring says raising the cost later is "a matter of re-deriving each slot at the
next login". That cannot be done for a document with several people, because each slot needs its own person's password.
Raising the cost of an existing document is therefore not part of this decision; the project is pre-release.
