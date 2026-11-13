# E10.2 spike: what a presenter mode can rely on in each shell

A throwaway test bench, not product code. It answers question 1 of `claudiaoffice-log/notes/e10-2-presenter-mode.md`
(and the technical half of question 5, the keys): **can the web client put a slide on a full screen, open a second
window for the audience, keep the two in step, and receive F5 and friends, in Firefox, in the GTK shell on Linux and in
the Neutralino shells on macOS and Windows?** The findings go into that note and into the decision log; the raw
reports go into `results/`.

Written 2026-11-13. Run in headless Chrome by the author (window opens, three message channels answer in about a
millisecond, keys arrive); **not run** in Firefox, WebKitGTK, WKWebView or WebView2: that is what this is for.

## What the code already says (before anybody runs anything)

* **GTK shell (`clients/linux/.../webpage.py`).** `javascript_can_open_windows_automatically` is off, and a new-window
  request to one of our own pages is loaded in the same view. So today `window.open` cannot give a second window; the
  shell needs a `create` handler (a small contract change). Fullscreen is not handled by the shell at all.
* **Neutralino shells (macOS, Windows).** The web app lives in an `<iframe>` of the shell page
  (`clients/*/tools/shell-page.template.html`) without `allow="fullscreen"`, so the web app's own fullscreen request
  is refused by the browser's rules unless that attribute is added. The `nativeAllowList` of the apps has only
  `app.exit`, `window.setMainMenu`, `events.on`, `extensions.*`, `app.broadcast`: `window.setFullScreen` and
  `window.create` are not allowed, so the shell could not act for the page either without new entries (and a contract
  message for them).

## Run it

All platforms need the page served from a loopback address; `serve.py` does that with the standard library only.

* **Any browser (Firefox first, then Chrome and Safari if you like):**
  `python3 serve.py`, then open `http://127.0.0.1:8777/index.html`. Allow pop-ups for that address.
* **Linux, GTK shell as it is today:** `python3 gtk/run_gtk.py today` (add `--frame` to see the frame wrapper).
  **With the changes a presenter mode would need:** `python3 gtk/run_gtk.py candidate`.
  Needs `python3-gi`, GTK 4 and WebKitGTK 6, which the Claudia GTK client needs anyway.
* **macOS:** `sh neutralino/run_macos.sh`. **Windows:** double-click `neutralino\run_windows.cmd`.
  Needs Node.js (downloads Neutralino's small binaries). The window opens the wrapper page, which shows the probe in a
  frame like the product's shell pages; the two radio buttons choose whether the frame has `allow="fullscreen"`. Run
  everything once with *no allow* (as the shells are today) and once with *allow="fullscreen"*, then use the
  Neutralino section of the page (the shell page does the work for the framed page, as the contract would).

On the page, go top to bottom: fullscreen, open the audience window, measure the round trip, list screens (if you have
two; with one, say so in the report), press the keys, then the manual verdicts. **Make report**, **Copy**, and put the
JSON in `results/<os>-<shell>-<date>.json`; add a few lines of your own in a `.md` next to it if something surprised you
(`results-template.md`).

## What the rows mean

| Section | Question behind it |
|---|---|
| 2 Fullscreen | Can a slide fill the screen and does Esc leave it? In a frame, only with `allow="fullscreen"`. |
| 3 Second window | Does `window.open` give a window, and do the two windows hear each other (BroadcastChannel, `postMessage`, `storage` events)? How fast? |
| 4 Several screens | Is the Window Management API there (Chromium only, as far as I know), or must the person drag the window? |
| 5 Keys | Which of F5, Shift+F5, Ctrl+F5, Alt+F5, Ctrl+Alt+N, Ctrl+Shift+P, F11 reach the page? Does F5 reload anyway (page loads grow)? |
| 6 Other | Screen Wake Lock, so the projector does not sleep during a talk. |
| 7 Neutralino | Can the shell go fullscreen and create a window when the framed page asks? |

## Files

`page/index.html`, `app.js`, `probe.js` (the probe), `audience.html` (the second window), `frame.html` (wrapper that
imitates the Neutralino shell page); `serve.py`; `gtk/run_gtk.py`; `neutralino/` (config and two scripts);
`results/`.
