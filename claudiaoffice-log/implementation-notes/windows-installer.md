# Windows installer (E8.1, D740-D745)

Branch `win-installer`, written 2026-11-17. **Nothing here has run on Windows.** What was run: the frozen server on
Linux (same spec), every unit test, ruff, mypy, actionlint. The first CI run on `windows.yml` is the real check.

## Parts

| Part | Where | Decision |
|---|---|---|
| frozen server | `packaging/windows/claudia-server.spec`, `server_entry.py` | D740 |
| smoke test over the websocket | `packaging/smoke_server.py` | D742 |
| packaged client | `clients/neutralino/src/packaged.ts`, `launch.ts`, `paths.ts`, `server.ts` | D741 |
| installer | `packaging/windows/claudia.iss` | D742 |
| service | `packaging/windows/service/claudia-service.xml` (WinSW) | D743 |
| staging, versions, pins | `packaging/windows/build.py`, `third-party.json` | D742 |
| CI and release | `.github/workflows/windows.yml`, `deb.yml` | D742 |
| consistency tests | `tests/test_windows_packaging.py` | |

## Choices worth knowing

* The client is the checkout's client plus `packaged.json`; it runs from a copy of its app folder in `%LOCALAPPDATA%\Claudia\run`.
* The service listens on 127.0.0.1:8765 and has its documents in `%ProgramData%\Claudia` -- not those of the person's own server (D743).
* The installer's version is the tag; for other builds `<package.json version>-dev.<run>+<sha7>`.
* The window step of the test job is `continue-on-error`: whether a runner can show a WebView2 window is unknown.
* The WinSW hash in `third-party.json` was computed from a download made while writing this, not from a published checksum.

## Not done

Signing (D744); file associations (the apps take no file on the command line); a launcher without a console window; MSI (D745); macOS installer; AI runtime (D745); one version number for the suite (the Linux `_version.py` and the client's `package.json` differ).
