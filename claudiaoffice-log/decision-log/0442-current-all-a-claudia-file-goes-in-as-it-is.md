---
id: D442
title: "A Claudia file from the computer goes into a place as it is, under its own id"
status: current
applies-to: all
date: 2026-11-14
round: "Opening files from the computer (branch one-server)"
supersedes: []
superseded-by: []
---

# D442 · A Claudia file from the computer goes into a place as it is, under its own id

**A `.claudia` file is uploaded like any file (D440); the answer names its app, id and title and says whether the
place already holds a document of that id. `POST /api/uploads/<token>/place` puts it into the app's folder, still
sealed and unchanged, and the person opens it with a name and password it already knows. It never overwrites: a
document of that id there already is refused (409), and the person opens that one or chooses another place. A
server that keeps its documents in memory cannot take a file in.**

**Notes.** The id is bound into the file's encryption (D431), so it cannot be renamed on the way in. The manifest is
read from a private temporary file before anything is placed, and the file is linked into place only if no file of
that name exists.
