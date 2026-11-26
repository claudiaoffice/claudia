---
id: D2009
title: "A picture's path is kept, for everybody who can open the document, unless the person says not to"
status: current
applies-to: all
date: 2026-11-25
round: "Bug eater, batch 5 (branch batch-5): SEC-27"
supersedes: []
superseded-by: []
---

# D2009 · A picture's path is kept, for everybody who can open the document, unless the person says not to

**Decided 2026-11-25** by the owner (SEC-27).

A picture taken in from the computer could carry the full path of its file. It was meant for the person who took it in
only, but only some ways out hid it: the document's content held it, so a viewer's snapshot, the sealed file and an
export carried the importer's folder names. On a single desktop install the path is useful: it says where a picture
came from.

**Rule.** The image dialog (Insert ▸ Image, the same in composes, computes and creates) has a box **"Don't save the
path"**, unticked, with the hint that everyone who can open the document sees it. Unticked, the path is kept and every
reader of the document sees it (Picture Properties). Ticked, the path sent is empty and nothing is kept. There is no
second rule per person any more: the person decides.

The box is there only where a path is known. A browser never knows it; the desktop shells choose the file with their
own dialog (D501) and now pass its path with the name. No migration: pre-release, nothing is converted.

**Notes.** The rule this replaces was never a decision of its own: it came in with the pictures (E10.8, server 0.14.0,
2026-11-07) as "the product decision that a colleague sees 'imported from disk'", and the code cited "D…" for it
(Picture Properties cited D141, which is about File ▸ Manage). It is gone with its per-person `to_data_for`. An empty
path is stored as none wherever a picture comes in (`ImageImport.from_data`).
