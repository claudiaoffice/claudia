# Windows installer

`claudia-office-<version>-windows-x64.exe`: the three apps (composes, computes, creates), the server they share, and an
optional Windows service. Decisions: D740-D745; notes: `claudiaoffice-log/implementation-notes/windows-installer.md`.

**Status: nothing here has run on Windows yet.** `.github/workflows/windows.yml` builds and tests it; its first run is the check.

## What is in it

| Part | Made by | Installed to |
|---|---|---|
| `claudia-server.exe` (Python and libraries inside) | PyInstaller, `claudia-server.spec` | `{app}\server` |
| web frontend | `npm run build` in `web/` | `{app}\web` |
| the three clients and `packaged.json` | `clients/neutralino` | `{app}\client` |
| `claudia-start.exe`, what the shortcuts start: node without a console window, its output in a log | MinGW `gcc`, `launcher/claudia-start.c` | `{app}\client` |
| Node.js | the version CI uses | `{app}\node` |
| service wrapper | WinSW 2.12.0 (pinned by SHA-256, `third-party.json`) | `{app}\service` |
| WebView2 bootstrapper | Microsoft; run only if the runtime is missing | temporary |

Per person (no administrator rights) or for all people (the wizard asks). Documents stay when the program is removed.

## The service (optional, off by default, all-people installs only)

`ClaudiaServer`, automatic start, LocalService, `127.0.0.1:8765`, documents in `%ProgramData%\Claudia\documents`,
logs in `%ProgramData%\Claudia\state\service`. The desktop apps use it when it runs (D504), so they then show *its*
documents, not the person's own (`%LOCALAPPDATA%\Claudia\documents`). To serve other computers, edit
`{app}\service\claudia-service.xml` (`--host`, a certificate); an update keeps your copy.

## Building by hand (on Windows)

```powershell
cd web; npm ci; npm run build; cd ..
cd clients/neutralino; npm ci; npm run build:windows; cd ../..      # and `neu update` in each apps/<app>, as CI does
uv run --locked --no-dev --with pyinstaller==6.21.0 pyinstaller --noconfirm --distpath dist --workpath build/pyinstaller packaging/windows/claudia-server.spec
python packaging/windows/build.py fetch-winsw build/WinSW-x64.exe
python packaging/windows/build.py fetch-webview2 build/MicrosoftEdgeWebview2Setup.exe
python packaging/windows/build.py launcher --out build/claudia-start.exe        # needs MinGW-w64's gcc (choco install mingw)
python packaging/windows/build.py stage --node (Split-Path (Get-Command node).Source) --winsw build/WinSW-x64.exe --launcher build/claudia-start.exe --webview2 build/MicrosoftEdgeWebview2Setup.exe --out build/stage
python packaging/windows/build.py installer --stage build/stage --version 0.3.0-dev.1 --numeric 0.3.0.1 --out dist/installer
```

`build.py version v1.2.3` prints a release's version (`--field numeric` the four-part one). Inno Setup 6 (`iscc`) must be installed. The exact commands CI runs are in `windows.yml`; use those if this list has drifted.

## Releasing

Tag `vX.Y.Z` and push. The workflow builds, tests on two Windows images, and attaches the installer to the release.
Other builds are `<package.json version>-dev.<run>+<sha>` and stay artifacts. The Debian workflow insists that the tag equals the Linux client's `_version.py`, so set that first.

## Signing (D744, not decided)

Unsigned, Windows SmartScreen warns on download. The workflow can sign through SignPath Foundation's free programme for open
source; it is **off** until you set these in the repository settings:

| Kind | Name | Meaning |
|---|---|---|
| variable | `SIGNPATH_ORGANIZATION_ID` | switches signing on |
| secret | `SIGNPATH_API_TOKEN` | the CI user's token |
| variable | `SIGNPATH_PROJECT_SLUG` | default `claudia` |
| variable | `SIGNPATH_SIGNING_POLICY_SLUG` | default `release-signing` |

Before applying, read SignPath's terms (signpath.org/terms) and check that the project's licences qualify (an OSI
licence), who approves releases, and the credit they ask for in the README. The certificate names SignPath Foundation as
publisher. The inputs of the signing step follow SignPath's documentation from memory and are unverified. Only the installer is
signed, not the programs inside it.

## Known limits

* The output of an app's start is in `%LOCALAPPDATA%\Claudia\<app>\state\launcher.log` (the run before: `launcher.log.old`); no console window shows it (D750).
* No file associations: the apps take no file on their command line.
* No AI runtime, no MSI, no per-app uninstall (D745).
