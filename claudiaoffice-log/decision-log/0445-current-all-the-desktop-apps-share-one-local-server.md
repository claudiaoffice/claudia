---
id: D445
title: "The desktop apps share one local server on a fixed port; it outlives its windows and stops ten minutes after nothing is connected"
status: current
applies-to: all
date: 2026-11-14
round: "One server for all three apps (branch one-server)"
supersedes: [D119, D161]
superseded-by: []
---

# D445 · The desktop apps share one local server on a fixed port; it outlives its windows and stops ten minutes after nothing is connected

**Since E8.5 (2026-11-25):** the server is a person's own, "Private on this computer": her three apps share it, on a
port of her account (D1621), and use a server they find there only when it proves to be hers (D1620). What follows
about one server for the computer, found by its port whoever started it, is what CODE-99 fixed.

**The three desktop apps of a person use one local server for all three apps, with one folder of documents and one of
state for the suite. The first app that needs it starts it; the others find it (a small file in the state folder
says where it runs, and D435's folder lock settles two starting at once). Its port is chosen at the first start and
remembered, so its address — and what the page keeps for that address — stays the same. Closing a window does not
stop it: it stops by itself (D434's `--exit-when-idle`, 600 seconds) once nothing has been connected for ten minutes.
While any of its windows is open a shell keeps a connection of its own (`/api/presence`), and a shell that finds the
server gone starts it again on the same port, where the pages reconnect.**

**Notes.** Owner, 2026-11-14: the owner doubted stopping "after five minutes of nobody doing anything": people come
back from coffee to an open window and a stopped server. That is not what D434 counts: an open document or front page
holds a connection, and while one is open the server is never idle, however long nobody types. The clock starts only
when the last page has closed. The front page did not hold its presence connection yet (fixed with this decision),
which would have caused exactly the confusion feared. A server that always runs (a login service) was the
alternative; it was not chosen because it is a background service nobody asked for. Supersedes D119 (the server never
outlives its shell) and D161 (an orphaned server on a killed Windows shell): a server left behind by a killed shell
now stops by itself. D115's side effect (a new port, so `localStorage` is lost, at every start) is gone too.
