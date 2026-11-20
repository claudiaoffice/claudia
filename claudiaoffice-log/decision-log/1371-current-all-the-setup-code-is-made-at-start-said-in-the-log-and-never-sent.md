---
id: D1371
title: "The setup code is made at each start with no administrator, said in the banner, the log and one file, and never sent by the server"
status: current
applies-to: all
date: 2026-11-20
round: "SEC-12: the first administrator needs a setup code (branch sec-12-setup-code)"
supersedes: []
superseded-by: []
---

# D1371 · The setup code is made at each start with no administrator, said in the banner, the log and one file, and never sent by the server

**Decided 2026-11-20** (mock-up panels 1, 2 and 4).

- **What it is.** 12 characters of Crockford's base32 (60 bits, `secrets`), shown in groups of four: `K7QM-4TXR-92HB`.
  Typed or pasted, case, dashes and spaces do not matter, and O counts as 0, I and L as 1.
- **When.** Made at every start that ends with no administrator (after D1375 and D1376 have run). It dies when the first
  administrator is named and when the server stops; a restart makes a new one.
- **Where.** In the start banner (so in the log of a container or a service), and in `admin/setup-code` under the
  server's state folder, readable by the server's own account only (0600, written like `admins.json`). The file is
  removed once an administrator exists. **The server never sends the code**: no answer of any request contains it.
- **How it is checked.** Compared in constant time after normalising (`hmac.compare_digest`). A wrong code is 403
  with a sentence that says where to look; the tries of `/setup` and of the check (D1372) are counted per address by
  the back-off of the sign-in (D1266), so too many get 429 with `Retry-After`. A code that was right but too late (an
  administrator was named meanwhile) is 409, and the page turns to the sign-in form with one line on top.
- **The status says whether one is needed:** `GET /api/admin/status` gains `setup_code: true` while nobody has been
  named. A page that talks to an older server (no such field) shows no field.
