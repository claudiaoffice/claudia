---
id: D1319
title: "The way back is taken before every jump and lives until the person goes on; its key is Ctrl+Shift+B"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1319 · The way back is taken before every jump and lives until the person goes on; its key is Ctrl+Shift+B

**Decided 2026-11-19** while building D1312, where the architecture note (`notes/e1-architecture.md`, §5) left details open.

* **Taken before every jump,** also when the thing is in the container already in view (a long text, a big sheet): the person may have scrolled, and the way back is *where the view was*, not only *which slide or sheet*. The session keeps the container and an *anchor* the view reports (composes: the first paragraph in sight; computes: the cell at the top left; creates: none, the slide is the container).
* **No destination, no chip:** when the view reports nothing and there is no container, there is nothing to go back to and no way back is offered.
* **Lifetimes:** the highlight of the thing keeps `POINT_MS`; the way back keeps until it is used, the person types, clicks into the text or the grid or the slide, or another jump takes its place; Esc lets go of it. Using it shows the container, then scrolls to the anchor, once.
* **Key:** *View ▸ Back where I was* is **Ctrl+Shift+B / Cmd+Shift+B**, the owner's first choice. The fallback Ctrl+Alt+B is *Text Box* in composes and creates, so it was not free. Chrome, Edge and Firefox use Ctrl+Shift+B (Cmd+Shift+B on a Mac) to show or hide the bookmarks bar, and Chrome on a Mac uses Cmd+Option+B for its bookmark manager. A page can take Ctrl+Shift+B over in Chrome and Firefox; Safari may keep Cmd+Shift+B for its own menu. **This was read from the browsers' documentation and was not tried in a real browser** (the build machine has none); the embedded WebKitGTK and WebView2 views of the desktop clients have no bookmarks bar. If the key proves taken, it is one line in the manifest.
* **Why not the old 'from' of the highlight:** the highlight state is cleared by a timer, so the two lifetimes cannot share one record (D1312 says so).
