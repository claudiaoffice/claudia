---
id: D156
title: "Proposal: Neutralino stays the working choice for the Windows and macOS shell (D42), now on evidence rather than on its documentation"
status: current
applies-to: all
date: 2026-11-07
round: "Neutralino on Windows and macOS (twenty-eighth round)"
supersedes: []
superseded-by: []
---

# D156 · Proposal: Neutralino stays the working choice for the Windows and macOS shell (D42), now on evidence rather than on its documentation

**Proposal: Neutralino stays the working choice for the Windows and macOS shell (D42), now on evidence rather than on its documentation.** Version 6.8.0 with Plotly 3.7.0 passed every automatic check on macOS (WKWebView) and Windows 11 (WebView2): Plotly bar, line, heatmap and 100,000-point WebGL, a native menu from a manifest, native file dialogs, theme, a bundled font and a cross-origin font, and start and stop of a server process.

**Notes.** **One machine per OS.** Still untested: a clean Windows 10 (WebView2 runtime), a screen reader on any OS, an older macOS, the allow-list, and a maturity check of the project (releases, maintainers, open issues for Wayland, IME and accessibility). The fallbacks of D42 (Tauri, pywebview, webview/webview, own shells) stay named and the adapter stays thin. The first WebGL chart on macOS took 857 ms against 50 ms afterwards.

*Written as a proposal; confirmed by the owner on 2026-11-10, since the code already follows it.*
