---
id: D446
title: "An import shows one progress bar for sending, reading and opening; the dialog comes as soon as a file is chosen"
status: current
applies-to: all
date: 2026-11-14
round: "One server for all three apps (branch one-server)"
supersedes: []
superseded-by: []
---

# D446 · An import shows one progress bar for sending, reading and opening; the dialog comes as soon as a file is chosen

**Choosing or dropping a file opens the import dialog at once, with one bar in three parts: sending the file
(measured: the browser counts the bytes), reading it on the server and opening the new document (neither can be
measured, so the part being done moves instead of showing an amount). The words under the bar say which part is
being done. Name, owner and password can be filled in while the file is on its way; Open becomes possible once the
file has arrived, is greyed again once clicked, and the dialog gives way to the document when it is open. Cancel
stops the sending; while the server reads the file there is no Cancel.**

**Notes.** Owner, 2026-11-14, on sheet 11: the sheet's version showed sizes, time left, an elapsed clock and a list of
steps — "more info than most users care". The upload uses `XMLHttpRequest`, because `fetch` cannot tell how far an
upload is. A screen reader hears each part once, not every percent; the moving stripes stop under reduced motion.
