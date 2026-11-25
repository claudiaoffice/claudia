# Review of `macos-installer.feature` (draft of 2026-11-25, E8.5)

How to answer: "ok" accepts my proposal; anything else replaces it. Suggested order: the `@core` scenarios first.

## A. How these scenarios are run

No Mac runner is connected (`ci.yml`'s macOS entry is switched off; `macos.yml` will be too). So:

* the parts of the package (layout, Info.plists, launcher scripts, `window.sh`, the installer's choices) by unit tests on
  any system, in CI (`tests/test_macos_packaging.py`, `clients/neutralino/tests/`);
* install, open, update, uninstall by `packaging/macos/test-install.sh`, which you run in a macOS virtual machine on your
  Mac; I cannot run it, and will say so in every delivery;
* "Open Anyway" for an unsigned package, the Dock icon and the German installer pages: by hand, in the VM.

## B. The matrix, walked

| Axis | Covered by | Left out, and why |
|---|---|---|
| States: fresh Mac / installed / installed with service / older version installed / app open / unsupported Mac | the scenarios | an installation moved by hand: not supported |
| Actors: an administrator of the Mac / any other person | install and uninstall need an administrator; opening an app is anyone's | |
| Operations: install, open, quit, update, uninstall | the scenarios | downgrade: allowed (E8.5, Q5), not tested |
| Clients: the macOS app | | |

## C. Questions (proposal first)

| Q   | Question                                                         | Proposal                                                                                                                                                                                                                                                                  | Answer |
| --- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| 1   | Uninstalling while apps of other people of the Mac are open.     | The uninstaller ends every claudia process of the Mac after its confirmation ("claudia's apps that are open, also those of other people of this Mac, are closed."); unsaved work does not exist (every change is kept as it is made).                                     | Yes    |
| 2   | What does the uninstaller remove from each person's own folders? | Only what is a copy: each person's `~/Library/Caches/Claudia`. Kept: documents, settings (`shell.json`, `state/`), logs.                                                                                                                                                  | Yes    |
| 3   | The uninstaller's last words.                                    | "claudia is removed. These folders are left: the shared documents in /Library/Application Support/Claudia/shared/documents, and each person's own documents and settings in ~/Library/Application Support/Claudia. Delete them if you no longer need them." (also German) | Yes    |
| 4   | Where the uninstaller lives.                                     | Applications ▸ Utilities, named "uninstall claudia" (E8.5, Q4).                                                                                                                                                                                                           | ok     |
| 5   | Version shown where?                                             | In each app's About dialog (as today) and in the installer's title ("claudia 0.5.0").                                                                                                                                                                                     | Yes    |
