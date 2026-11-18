---
id: D785
title: "Two ways to delete a style: assign another style, or re-base on another style"
status: current
applies-to: all
date: 2026-11-18
round: "Deleting and hiding styles (E1.10)"
supersedes: [D784]
superseded-by: []
---

# D785 · Two ways to delete a style: assign another style, or re-base on another style

**Decided 2026-11-18** by the owner, after seeing D784's three ways: *keep their look* was a rename in disguise, the same look under the same parent with a new name, and *go back to no style* is only one choice of a style to assign, because in Claudia nothing is ever without a style and the body paragraph is among the styles.

**Two ways, offered in this order, the first one preselected:**

1. **Assign another style** (`assign`). The person names a style of the same kind; everything that has the deleted style gets it instead and looks like it. A style that was based on the deleted one is based on the named style, each as it was, and loses what the deleted style said. So "every place that pointed at the deleted style points at the named one". **Looks change**, and the dialog counts them before anything happens ("14 paragraphs and 1 style will look different"; `assign_changes_look`). The dialog preselects the plain style of the kind (`StyleBook.fallback`: *Body text* for a paragraph, *Plain box* or *Plain image* for a box): that is what "no style" means in a document, and what other office software falls back to.
2. **Re-base on another style** (`rebase`). Everything keeps looking exactly as it does, but is built on the style the person names: it follows that style from now on, except where the deleted style differed. What had the deleted style itself moves to a style "<name> (kept)" under it, waiting for its name (D781). The dialog explains it with an example: "Quote is italic and indented. Re-based on Note it stays italic and indented, and takes on any later change to Note's font and size."

**The named style** is of the same kind, and neither the deleted style nor one based on it (that would be a cycle). It may be left out only when nothing has the style and nothing is based on it: then the style just goes.

**D226 stands as amended by D784:** a deletion never leaves a dangling reference; only *assign* changes looks, on purpose and said first.

Everything else of D780–D782 stands: only document styles are deleted, the others are hidden; one step in the history, undone as one; a style somebody began to use meanwhile refuses the whole step.
