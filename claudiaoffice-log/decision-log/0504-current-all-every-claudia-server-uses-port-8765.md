---
id: D504
title: "Every Claudia server on a computer uses port 8765: the desktop apps' shared server and ./start.sh alike"
status: current
applies-to: all
date: 2026-11-15
round: "The three desktop clients: one server, files, printing (branch clients)"
supersedes: []
superseded-by: []
---

# D504 · Every Claudia server on a computer uses port 8765: the desktop apps' shared server and ./start.sh alike

**The shared local server of the desktop apps (D445) listens on 127.0.0.1:8765, the port `./start.sh` uses. A shell
first looks there: a Claudia server of the same version on 8765 is this computer's server, whether a desktop app or
`./start.sh` started it, and the windows connect to it. Only when something that is not a Claudia server holds 8765
does the shell start its server on another port (the one it remembered, or a free one) and log why.
`CLAUDIA_SERVER_PORT` sets another port for a person who needs 8765 for something else, and for tests. This replaces
D445's "its port is chosen at the first start"; everything else in D445 stands.**

**Notes.** Owner, 2026-11-15: all three apps still started a server on a random port, where 8765 had been agreed; asked
whether the desktop server may share the port with `./start.sh`, he answered that `./start.sh` stands for a cloud server
to which desktop and web clients connect, so all servers should have the same port. Consequences: with a desktop server
on 8765, `./start.sh` cannot bind the port until that server has stopped by itself (ten minutes after its last window,
D445) — stop the desktop apps first, or set `CLAUDIA_SERVER_PORT` for them. A desktop server left over from before this
decision, on its old random port, is still found and used until it stops by itself; the next start is on 8765. The
`localStorage` of a page belongs to its address, so what a page kept on the old port is not seen on 8765 (once).
