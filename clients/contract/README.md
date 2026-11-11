# The shell contract

How a native shell (Linux today; Windows and macOS later) and the web page it shows talk to each other (E5.12). The
page is the same everywhere; each shell draws the menus of its platform and tells the page to do what they say.

Files: `shell-contract.v1.schema.json` is the contract (JSON Schema, draft 2020-12). Shells and the web app check their
messages against it.

## Messages

All messages are JSON objects with a `type`. A message is at most 64 KiB. A receiver **ignores** types it does not know.

| type | from | meaning |
| --- | --- | --- |
| `hello` | page | The page is there: `contract` (the highest version it speaks, a whole number), `app` (`composes`, `computes`, `creates`; left out by a page that does not know yet which app its server runs, in which case the shell takes it to be its own). May also list the versions it speaks (`supported`). |
| `welcome` | shell | Answer to `hello`: the `contract` version both will use, the shell's version and its `capabilities` (`native-menu`, `actions`; `connect` and `servers` when the shell can connect the window to another server and keeps the list of servers). |
| `action` | shell | Carry out the menu action `action` (an id such as `file.save`). `target` (`on` or `off`) is given for choices that are ticked or not: asking for the state that is there already does nothing. |
| `action_state` | page | Which actions are `enabled`, `checked` or relabelled now. Only the actions named change. |
| `connect` | page | Show the server at `address` (as a person typed it, or an origin from the list) in this window. The shell checks it and either loads that server's page or answers `connect_failed`. Only sent when the shell offers `connect`. |
| `connect_failed` | shell | The connection asked for was not made: `code` (`bad_address`, `insecure`, `unreachable`, `not_claudia`, `wrong_app`, `certificate_expired`, `certificate_invalid`, `not_trusted`) and a `message` fit to show to the person. |
| `servers` | shell, page | The list of servers of this window's app: entries of `origin`, `label`, `custom` (the person named it) and `local` (the server on this computer, which only the shell lists). The shell sends it after `welcome`; the page sends it back when the person changes it (renames, say) and never before it has received the shell's. Only exchanged when the shell offers `servers`. |
| `error` | either | Something in the other side's message was wrong: `code` (`bad_json`, `bad_message`, `unsupported_contract`, `unknown_action`, `internal`) and a `message` for the log. `unsupported_contract` lists what the sender supports. |

Action ids say what an action *does*, not where it sits in a menu (`file.save`, `view.page`, `assistant.ask`): lower
case, namespaced, so a menu can be rearranged in one shell without a change to the contract.

## Versioning

* **Additive changes keep the version**: a new optional field, a new message type (receivers ignore what they do not
  know), a new action id, a new capability, a new error code.
* **Anything else is a new version with a new file** (`shell-contract.v2.schema.json`): removing or renaming a field,
  making an optional field required, changing what a field means. The old file stays, unchanged, for as long as a
  shell or the web app still speaks it.
* **Negotiation.** The page says the highest version it speaks in `hello`; the shell answers with the highest version
  both speak in `welcome`, or with `unsupported_contract` and the versions it does support. A shell that supports
  several versions simply lists them (`SUPPORTED_VERSIONS` in `contract.py`).
* A change to the schema needs a line in `clients/linux/CHANGELOG.md` and a test in `clients/linux/tests/test_contract.py`
  (which checks the Python code and the schema against the same messages).

## Transports

The messages are the same JSON text on every platform; what carries them differs with the shell's web view.

* **WebKitGTK (Linux).** The shell registers `window.webkit.messageHandlers.claudia`, which the page posts to, and
  calls `window.__claudiaShell.receive(text)`, which the page registers.
* **Neutralino (macOS; Windows to follow), D251.** The web app is shown in a frame of the shell's own page, so the two
  use `postMessage` with the message as text. The shell page accepts a message only from its own frame and only from
  the origin it opened there; the web app accepts one only from its parent window and only when that is a page on
  this computer's loopback (the shell page is served by Neutralino from there).
* A plain browser tab has neither: the page never becomes ready and draws its own menus.

## Who implements it

The shell side is `claudia_shell_gtk.contract` and `bridge` (Linux) and `clients/macos/src/contract.ts` and `bridge.ts`
(macOS; its tests judge every message by this schema and by the code, and the two must agree). The web app speaks the
contract itself (`web/app/lib/shell-bridge.ts`), on the start page as well as in a document.

## Connecting to other servers

A shell shows one server at a time and never lets the page navigate away from it (a link would be handed to the
person's browser). The page therefore asks: `connect` with an address, and the shell answers by loading that server's
page (a fresh `hello` follows) or with `connect_failed`. What the shell checks is the shell's business (the Linux
shell: https or this computer, the certificate, the same app); the page only shows `message`. A window connects to
servers of its own app only.
