# The shell contract

How a native shell (Linux today; Windows and macOS later) and the web page it shows talk to each other (E5.12). The
page is the same everywhere; each shell draws the menus of its platform and tells the page to do what they say.

Files: `shell-contract.v1.schema.json` is the contract (JSON Schema, draft 2020-12). Shells and the web app check their
messages against it.

## Messages

All messages are JSON objects with a `type`. A message is at most 64 KiB. A receiver **ignores** types it does not know.

| type | from | meaning |
| --- | --- | --- |
| `hello` | page | The page is there: `contract` (the highest version it speaks, a whole number), `app` (`composes`, `computes`, `creates`). May also list the versions it speaks (`supported`). |
| `welcome` | shell | Answer to `hello`: the `contract` version both will use, the shell's version and its `capabilities` (`native-menu`, `actions`). |
| `action` | shell | Carry out the menu action `action` (an id such as `file.save`). `target` (`on` or `off`) is given for choices that are ticked or not: asking for the state that is there already does nothing. |
| `action_state` | page | Which actions are `enabled`, `checked` or relabelled now. Only the actions named change. |
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

## Who implements it

The shell side is `claudia_shell_gtk.contract` and `bridge` (Linux). The web app does not speak the contract yet; for
now the Linux shell injects a page adapter that does it on the page's behalf (`clients/linux/src/claudia_shell_gtk/data/shim.js`).
