# Claudia for Linux (claudia-shell-gtk)

The native client of Claudia for the GNOME desktop: a thin shell of GTK 4, libadwaita and WebKitGTK 6.0 around the one
web frontend (decisions D42–D44). The shell draws what a native application should draw (window, header bar, menus,
About, dialogs, clipboard); everything inside the document is the web app.

**One shell, three applications.** The shell itself knows no app: `identity.py` (the one table that names them),
`manifest.py` (their menus) and `apps/<app>/` (desktop entry, icon, AppStream metadata) are all that tells
**Claudia Composes**, **Claudia Computes** and **Claudia Creates** apart. A Linux install has three start buttons, one
per app (`claudia-composes`, `claudia-computes`, `claudia-creates`; one `.deb` holds all three). A window is one app
and talks only to servers of that app.

```
clients/
  contract/            the shell contract: JSON schema, versioned, shared by every shell (see its README)
  linux/
    src/claudia_shell_gtk/
      contract.py      parse and build contract messages              (no GTK)
      manifest.py      the menus: one list of actions per app          (no GTK)
      bridge.py        the conversation with the page                  (no GTK)
      server.py        start, wait for and stop the local server       (no GTK)
      launch.py        which server, which frontend, or what is missing (no GTK)
      cli.py           the command line: --server, --debug, --version  (no GTK)
      servers.py       which addresses may be connected to, the list   (no GTK)
      connection.py    can this window connect to that server?         (no GTK, blocks: worker thread)
      connector.py     connect, ask about a certificate, switch        (no GTK)
      trust.py, x509.py  trusted certificates, reading a certificate   (no GTK)
      settings.py      shell.json: language, servers, trusted certs    (no GTK)
      paths.py, urls.py, identity.py                                   (no GTK)
      window.py        the window: header bar, menus, pages            (GTK)
      app.py           the application, accelerators, start and stop   (GTK)
      webpage.py       the WebKit view and its rules                   (GTK + WebKit)
      data/            window.ui (layout), webroutes.json
    apps/<app>/        desktop entry, icon, AppStream metadata, per app
    tests/
```

## Running it from a checkout

```
uv sync                                   # the server's Python 3.14 environment: .venv
(cd web && npm ci && npm run build)       # the web frontend: web/.output/public
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0      # Fedora: python3-gobject gtk4 libadwaita webkitgtk6.0
./start-linux-client.sh computes                # or composes, creates; builds the frontend first
# or, by hand:
cd clients/linux && PYTHONPATH=src /usr/bin/python3 -m claudia_shell_gtk computes
```

Installed (the `.deb`, or `pip install` of this directory) the same thing is `claudia-composes`, `claudia-computes` or
`claudia-creates`. All take:

| Option | Meaning |
| --- | --- |
| *(none)* | Start this app's own server on this computer and show it. |
| `--server URL` | Start no server; connect to that one (`https://host[:port]`, or a bare `host[:port]`, which means https; plain `http://` is only accepted for this computer). It is checked like a server typed into the page and remembered in this app's list of servers. |
| `--debug` | More logging and the web inspector. |
| `--version` | `claudia-computes 0.1.0`. |

There is no command that asks which app to open; `python3 -m claudia_shell_gtk` needs the app as its first argument.

Documents are kept in `$XDG_DATA_HOME/claudia/<app>/documents` and the server's state and log in
`$XDG_STATE_HOME/claudia/<app>` (`server.log` is where to look when the window says the server did not start).

## Other servers

On the start page, the **Servers** list shows **This computer** (the server this window started; not there with
`--server`) and every server this app has connected to; **+ Connect to a server…** takes an address. In this shell the
page does not navigate there itself (the shell never lets its view leave the server it shows): it sends the shell a
`connect` message, and the shell, in this order, stops at the first step that fails (messages are in `connection.py`):

1. **Address.** `https`, or `http` only for this computer (`servers.parse_address`).
2. **Reach it, check the certificate.** The server answers `/api/health` over TLS. A certificate the system trusts is
   fine. One nobody vouches for (self-signed, an unknown authority, a name that is not the server's) is offered to the
   person ("Trust this server?", showing the SHA-256 fingerprint) and, once trusted, pinned **for that one origin**
   (`trust.py`, `shell.json`); a different certificate later is asked about again. An expired or not-yet-valid one is
   never offered.
3. **Same app.** `/api/docs` names the app, which must be this window's (a server that keeps its list behind a secret
   does not say; the page's `hello` is checked again when it loads).
4. **Switch.** The window shows that server, and the address is remembered in the list of this app (`shell.json`: one
   list per app; never a password or an access secret).

The web view accepts a certificate the system does not trust only if it is exactly the pinned one
(`trust.may_override`, `WebPage._load_failed_with_tls_errors`). The shell, not the page, owns the list: the page's own
`localStorage` is per origin and cannot span servers. The page may rename entries and hands the list back; only what
passes `servers.sanitize` is kept.

**Open point:** the "Trust this server?" dialog is designed (`claudiaoffice-log/notes/mockups/connect-and-trust.svg`)
but not built until the design is agreed. Until then a certificate that nobody vouches for is refused with an
explanation, and nothing is trusted unasked.

| Variable | Meaning |
| --- | --- |
| `CLAUDIA_SERVER_PYTHON` | The Python 3.14 that runs the server. Default: `.venv/bin/python` of the checkout. |
| `CLAUDIA_WEB_DIR` | The built web frontend. Default: the one shipped in the package, else `web/.output/public`. If set, it is the only candidate: a wrong path is reported, not replaced. |
| `CLAUDIA_DEBUG` | `--debug` sets it: more logging, the web inspector, the page's console on stdout. |
| `CLAUDIA_CLIENT_PYTHON` | For `scripts/check_debt.py`: the interpreter that runs this client's tests. |

## Two interpreters

* **The server runs on Python 3.14** and stays there. It is a separate process with its own environment.
* **The shell runs on the Python of the distribution** (3.12 on Ubuntu 24.04), and must never make a person upgrade it.
  `requires-python` is `>=3.12`; ruff and mypy are set to 3.12 for this directory (`pyproject.toml`), so syntax and
  library features newer than 3.12 are caught. PyGObject, GTK, libadwaita and WebKitGTK come from the distribution, not
  from PyPI (a wheel would need a compiler and the GTK headers), so the shell is *not* part of the uv workspace.

The shell starts the server as `<server python> -m claudia_server --model claudia_composes:TextModel --host 127.0.0.1
--port <free port> --no-tls --web <frontend> ...` and shows `http://127.0.0.1:<port>`. The page and its WebSocket have
the same origin, so no cross-origin settings are needed. The connection is plain because it never leaves the computer.

## How it works

* **Native menus from the manifest.** `manifest.py` lists every action once (id, label, who carries it out, keys). The
  menus in `window.ui` are generated from it (D4: File, Edit, Tools, Help; Undo and Redo in Edit, D54; Cut, Copy and
  Paste there too, D74). Layout stays in GtkBuilder XML (D27), labels are marked translatable. An action is carried out
  by **the page** (the shell sends an `action` message), **the web view's editing commands** (cut, copy, paste) or
  **the shell** (quit, About).
* **One window class, any app.** `window.ui` has one menu button per menu id; the window gives each the menu of the
  app's manifest when it is created (`ClaudiaWindow._attach_menus`), so the layout and the GTK class are the same for
  every app. The web app speaks the shell contract itself (D121, `web/app/lib/shell-bridge.ts`).
* **Rules of the web view (`webpage.py`, `urls.py`).** The view never leaves the server's origin; links to other sites
  open in the default browser (web and mail addresses only); permission requests are denied; nothing contacts another host by itself
  (no DNS prefetching, WebRTC or media streams); downloads go to the Downloads folder under a name the page cannot use to escape it and never overwrite a file.
* **The server never outlives the window.** It runs in its own process group, which is ended with the window, and it
  asks Linux to send it `SIGTERM` when the shell dies, however the shell dies (tested with `kill -9`).

## Tests

```
cd clients/linux
xvfb-run -a /usr/bin/python3 -m pytest        # everything; needs python3-pytest and python3-jsonschema
python3 -m pytest -m "not gtk"                # without GTK and a display
xvfb-run -a python3 -m pytest -m e2e          # only the end-to-end test
```

Tests marked `gtk` need GTK 4, libadwaita 1.5+ and a display (Xvfb is enough) and skip themselves otherwise. The `e2e`
test starts the real server and the built frontend, creates a document through the page's Open dialog, drives it with
the native actions and checks that the server is gone afterwards; it skips itself when `.venv` or the frontend build is
missing. `tests/conftest.py` asks for software rendering and turns WebKit's own sandbox off, for tests only.
`scripts/check_debt.py` runs the client's types and tests too; CI has a Linux-only job for it.

## Compatibility notes

Things that differ between the interpreters and libraries, found while building this:

1. **PyGObject and the distribution.** Only the distribution's Python has `gi` for the system GTK (`/usr/bin/python3`).
   Another `python3` first in `PATH` (pyenv, uv, conda) usually cannot import it.
2. **libadwaita 1.5 is the floor** (`Adw.AboutDialog`; Ubuntu 24.04 has 1.5.0). Nothing newer is used. `Adw.Spinner` and
   other 1.6 widgets are avoided; a `GtkSpinner` does the same.
3. **`claudia-client` cannot be imported by the shell**: it needs Python 3.14 and depends on `claudia-core`. That is why
   the shell does not talk to a server itself; the page does. For remote servers the shell only *checks* them, with
   what the standard library has (`ssl`, `http.client`), and reads certificates with its own small DER reader
   (`x509.py`) instead of the client's `TlsPolicy`.
4. **The root configuration is 3.14.** Ruff and mypy at the repository root target 3.14, so this directory has its own
   targets; `uv run mypy` is run from `clients/linux` with `--project` so that uv does not create an environment here.
5. **Sphinx** documents the shell's GTK-free modules only; autodoc of the GTK modules would need `gi` mocked.
6. **`preexec_fn` is not used** to tie the server to the shell (unsafe with threads, and GTK has threads); a two-line
   launcher sets `PR_SET_PDEATHSIG` and then becomes the server. Linux ties that signal to the *thread* that started the
   process, so the server is started from the main thread.
7. **WebKit's URL patterns cannot name a port**, so the injected script is admitted for the host and checks
   `location.origin` itself.
8. **WebKit's network session is shared** by all views of a process: each page handles only its own downloads and lets
   go of the session when its window closes.
9. **Containers and CI:** WebKit's bubblewrap sandbox and GL may not work there (`WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1`,
   `LIBGL_ALWAYS_SOFTWARE=1`, `GSK_RENDERER=cairo`); the tests set them, the shell never does.
10. **Accelerators.** The page handles Ctrl+S, Ctrl+Z and Shift+F10 itself; binding them natively too would run them
    twice. The shell binds only Ctrl+O, Ctrl+Shift+S, Ctrl+Q and F1.
11. **Layout.** The web page lays out its menu bar in a grid row; the adapter hides it (`visibility`, height 0) instead
    of removing it.

## Not yet

Windows and macOS shells (D44, Neutralino); the "Trust this server?" dialog (designed, not built); removing a trusted
certificate again; the native *Save As* dialog (a
download goes to the Downloads folder with a message); native cut/copy/paste/Ctrl+S key bindings; translations (the
labels are marked, no catalog exists); Flatpak or another way to ship the frontend and the 3.14 interpreter with the
shell; Wayland and screen-reader behaviour, which were not checked outside Xvfb.
