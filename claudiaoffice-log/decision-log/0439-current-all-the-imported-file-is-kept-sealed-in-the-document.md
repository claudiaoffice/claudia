---
id: D439
title: "The imported file is kept, sealed, in the document file; the person may say not to"
status: current
applies-to: all
date: 2026-11-14
round: "Opening files from the computer (branch one-server)"
supersedes: []
superseded-by: []
---

# D439 · The imported file is kept, sealed, in the document file; the person may say not to

**By default the file a document was imported from becomes part of the document: the entry `content/original.bin`
of the `.claudia` file, sealed with the content key and bound to the document's id (`write_original`,
`read_original` in `claudia-container`). Every later write of the file carries it along. Whoever may read the content
may read it. The import dialog has "Keep the file inside the document", ticked; unticked (`keep_original: false` in
`hello`), nothing is kept and a download is written anew (D441). A store without files (memory) keeps it in memory.**

**Notes.** D217 chose "a retained original-file blob over reopening a path that may have moved or been deleted"; the
patching writers of D217, D371, D402, D403, D412, D413 and D219 all take that original, and nothing kept it until
now. The owner, 2026-11-14: "an imported document should keep the original import file as part of itself to allow
error-free round trips", and the person may switch it off. The entry is additive: the format stays
`claudia-document 1`, and older code already carries unknown entries along when it rewrites a file.
