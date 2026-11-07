# E0.3 shell test report (copy this file, one per machine and shell)

Name the copy `<os>-<version>-<shell>.md`, put it next to the JSON report from the window.

## Machine
- OS and exact version (Windows: `winver`; macOS: Apple menu ▸ About; Linux: distribution, GNOME version, Wayland or X11):
- Real machine or VM:
- Display(s): resolution and scale (100 / 125 / 150 / 200 %), second monitor with another scale?
- Keyboard layout, input method tried, screen reader used:
- Shell: GTK + WebKitGTK / Neutralino (version shown in the Environment table):
- Web view on this machine (WebView2 version on Windows, Safari version on macOS: the user agent line):

## Setup
- Did the wrapper script work first time? What did you have to install (Node, uv, WebView2 runtime)?
- Did Windows SmartScreen or macOS Gatekeeper warn about the Neutralino binary? How many steps to get past it?
- Download size of what `neu update` fetched (MB, `bin` folder):

## Automatic checks (from the report, only exceptions)
| Check | Result | Notes |
|---|---|---|
| | | |

## Manual rows (anything not "works")
| Row | Verdict | What I saw |
|---|---|---|
| Plotly events and hover (real mouse) | | |
| Menu from the manifest (native? shortcuts?) | | |
| File dialogs | | |
| About dialog | | |
| Dark and light mode | | |
| Dead keys and AltGr | | |
| Input method | | |
| Clipboard | | |
| Spellcheck and context menu | | |
| Drag and drop of text | | |
| Screen reader | | |
| Window behaviour | | |
| Display scale | | |
| Docked panel | | |
| Printing | | |
| Focus and keyboard | | |

## Numbers
- Seconds from launch to a visible window:
- Seconds to the first chart:
- Size of the installed shell without the page (MB):
- Leftover server process after the run? (yes / no)

## Overall
- Would you ship the app with this shell on this OS? What is the one thing that bothers you most?
