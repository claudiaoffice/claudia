# Claudia — code map

> **Stale.** Written 2026-11-02 at commit `842d739`, when the repository held six packages and no shell. At
> `54d1245` there are **ten** packages (`claudia-ai`, `claudia-container`, `claudia-fonts`, `claudia-typeset` have
> been added), a Linux client under `clients/`, and a shell contract under `clients/contract/`. The narrative below is
> kept because the request path, the extension points and the small findings are still broadly right; the numbers and
> the "not in the repo yet" list are not. Regenerate rather than trusting the tables.

## What the repo is, and is not

A uv workspace of Python 3.14 packages plus a Nuxt 4 single-page web app. It runs end to end: a server holds
documents, the web app edits a workbook through a versioned WebSocket protocol, people see each other's presence and
locks, and the `ai` user takes part.

*At `842d739`, not in the repo yet:* GTK or any desktop shell, the encrypted container, formulas, a real model or
OpenVINO engine, the remote AI boundary, skills.md and persona.md, restore-with-consent on the wire, workers, and
xlsx/ODF. *Of those, the shell, the container, formulas and the OpenVINO engine have since been built; the rest have
not.*

## Dependency flow

```
claudia-core            stdlib only, enforced by packages/claudia-core/tests/test_purity.py
  ^
  |-- claudia-computes  (imports core)
  |-- claudia-composes  (imports core)
  |-- claudia-creates   (imports core)
  |-- claudia-server    (imports core and the app packages; fastapi, uvicorn, websockets, cryptography)
  '-- claudia-client    declares core but imports nothing from it
web/  --WebSocket, JSON, protocol v1-->  claudia-server
```

Added since: `claudia-container` (crypto and the file format, no network code), `claudia-fonts`, `claudia-typeset`
(which depends on `claudia-fonts`), and `claudia-ai` (which knows nothing of documents). `clients/linux` is outside
the uv workspace on purpose, because it runs on the distribution's Python 3.12 (D116).

## How a typed cell travels

1. `web/app/lib/session.ts` calls `Link` in `protocol.ts` with `set_cells {sheet, cells:[{row,col,input}], base}`.
2. The WebSocket route `/api/docs/{doc_id}/ws` in `app.py`; `Gateway.admit` checks the `hello` frame, then
   `Gateway.serve` runs the connection.
3. `hub.Connection.handle(raw)` parses the frame and calls `MethodTable.dispatch(ctx, name, params)`.
4. `computes._set_cells` turns the typed text into typed content and calls
   `ctx.document.execute(SetCells(…), author=ctx.user, base=base)`.
5. `Document.execute` checks `base` (stale edit), checks locks for everybody including `ai`, applies the command,
   appends a log entry, records the inverse for per-author undo, and emits events.
6. `HostedDocument` turns events into pushed frames with audience rules and the web `Session` updates its replica.

**This path is still exactly right**, and step 3 is where the authorisation gap of SEC-10 sits: `dispatch` does not
know what the calling account may ask for.

## Where things live

| Concern | Files |
|---|---|
| Commands, schema versions, upcasters, Batch, Redacted, Checkpoint, Restore, Switch | `claudia_core/commands.py` |
| The log, lines (branches), forks, the path of a revision | `claudia_core/log.py`, `revision.py` |
| The Document: execute, undo and redo, checkpoints, restore, `switch_to`, `lines`, `discard_side_history`, `redact`, presence, locks, chat, the snapshot cache, the manifest check | `claudia_core/document.py` |
| Per-author undo | `claudia_core/history.py` plus `Command.shifted_by` |
| Region, presence, locks | `claudia_core/region.py`, `presence.py`; implementations per app |
| The storage seam | `claudia_core/store.py`; server side `hub.DocumentProvider`, `sealed.SealedDocuments` |
| Users and roles | `claudia_server/auth.py`; the real directory is now inside the document |
| The wire protocol | `claudia_server/protocol.py`; app methods in `computes.py`, `composes.py`, `creates.py` |
| HTTP, the static web app, the host guard | `claudia_server/app.py`, `hosts.py` |
| TLS | `certs.py`, `redirect.py`, `state.py`; client side `claudia_client/trust.py` |
| The AI participant | `assistant.py`, `standin.py`, `standin_text.py`, `model_engine.py`; the model in `claudia-ai` |
| The command line | `claudia_server/cli.py` |
| Styles | `claudia_core/css.py`, `styles.py`; hosts in `web/app/lib/*-style-host.ts` |

## Extension points

- **A new app:** subclass `DocumentModel`, write `Command` subclasses and a `Region`, register them in a
  `CommandRegistry`, then give the server a method table and extend `apps.methods_for`.
- **A real model:** implement the engine seam. *The constraint noted here at the time — that `plan` was synchronous
  and would stall every document — was fixed by adding `AsyncEngine.plan_async`.*
- **The container:** implement `DocumentStore`, `DocumentProvider` and `UserDirectory`. *Done: `SealedDocuments`.*
- **Formulas:** `entry.parse_input` is the single door where `=…` is parsed. *Done.*
- **The remote AI (D8):** the doc-server-dials-AI-server socket does not exist.

## Things to know and small findings

1. **Python 3.14 syntax.** The code uses `except A, B:` without parentheses (PEP 758). Any tool that parses it needs
   3.14; a 3.13 interpreter reports a syntax error in 14 files and is wrong. `uv python install 3.14` is the fix.
2. **Web tests need `npx nuxt prepare` first.** After a fresh `npm ci`, vitest fails on a missing
   `web/.nuxt/tsconfig.app.json`. `npm test` alone does not create it.
3. **Build output is tracked.** `web/dist/` holds 26 tracked files while the build goes to `web/.output/public`
   (CODE-02). *Still true.*
4. **README is stale.** *Still true (CODE-03).*
5. **`claudia-client` lists `claudia-core` as a dependency but imports nothing from it.**
6. **`apps.methods_for` is hard-coded per app**; composes and creates have since been added to it.
7. pytest warns that Starlette's `TestClient` with `httpx` is deprecated in favour of `httpx2`.

## The generator

`code-map-api.md`, the full listing of every module, class and function, was generated by this script and is not
copied into the log (see `README.md` here). The script is kept so the map can be regenerated. **It needs two changes
first:** `PACKAGES` is still the six of `842d739` and should read the workspace members from `pyproject.toml`, and it
belongs in `scripts/codemap.py` next to `check_debt.py` and `api_surface.py`.

```python
"""Extract a code map (modules, public API, internal imports) from the claudia packages.

Usage: python3.14 -I codemap.py REPO_ROOT > map.md
Needs Python 3.14 to parse the repo (it uses ``except A, B:`` without parentheses, PEP 758).
Reads source only through ast; never imports the repo.
"""

import ast
import sys
import tomllib
from pathlib import Path

root = Path(sys.argv[1])
PACKAGES = [
    "claudia-core",
    "claudia-computes",
    "claudia-composes",
    "claudia-creates",
    "claudia-server",
    "claudia-client",
]


def first_line(doc):
    if not doc:
        return ""
    return doc.strip().splitlines()[0].strip()


def sig(fn):
    args = fn.args
    names = [a.arg for a in args.posonlyargs + args.args]
    if args.vararg:
        names.append("*" + args.vararg.arg)
    names += [a.arg for a in args.kwonlyargs]
    if args.kwarg:
        names.append("**" + args.kwarg.arg)
    names = [n for n in names if n not in ("self", "cls")]
    return f"({', '.join(names)})"


def internal_imports(tree, own):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top.startswith("claudia_") and top != own:
                found.add(top)
        elif isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split(".")[0]
                if top.startswith("claudia_") and top != own:
                    found.add(top)
    return found


def external_imports(tree):
    std = sys.stdlib_module_names
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            top = node.module.split(".")[0]
        elif isinstance(node, ast.Import):
            top = node.names[0].name.split(".")[0]
        else:
            continue
        if top not in std and not top.startswith("claudia_"):
            found.add(top)
    return found


def local_imports(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def describe_module(path, own):
    src = path.read_text()
    tree = ast.parse(src)
    lines = src.count("\n") + 1
    out = {
        "lines": lines,
        "doc": first_line(ast.get_docstring(tree)),
        "classes": [],
        "functions": [],
        "all": None,
        "ext": sorted(external_imports(tree)),
        "pkgs": sorted(internal_imports(tree, own)),
        "local": sorted(local_imports(tree)),
    }
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "__all__":
                    try:
                        out["all"] = list(ast.literal_eval(node.value))
                    except Exception:
                        pass
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            bases = []
            for b in node.bases:
                try:
                    bases.append(ast.unparse(b))
                except Exception:
                    pass
            methods = [
                n.name + sig(n)
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not n.name.startswith("_")
            ]
            out["classes"].append(
                (node.name, bases, first_line(ast.get_docstring(node)), methods)
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            kind = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            out["functions"].append((kind + node.name + sig(node), first_line(ast.get_docstring(node))))
    return out


def main():
    for pkg in PACKAGES:
        mod = pkg.replace("-", "_")
        base = root / "packages" / pkg / "src" / mod
        print(f"\n## {pkg}\n")
        pyproject = root / "packages" / pkg / "pyproject.toml"
        if pyproject.exists():
            project = tomllib.loads(pyproject.read_text())["project"]
            deps = project.get("dependencies", [])
            print(f"Dependencies: {', '.join(deps) if deps else 'none (stdlib only)'}\n")
        mods = {}
        for path in sorted(base.glob("*.py")):
            if path.name == "_version.py":
                continue
            mods[path.stem] = describe_module(path, mod)
        print("| Module | Lines | Role | Imports (other claudia pkgs / third party) |")
        print("|---|---|---|---|")
        for name, info in mods.items():
            deps = ", ".join(info["pkgs"] + info["ext"]) or "-"
            print(f"| `{name}.py` | {info['lines']} | {info['doc']} | {deps} |")
        print()
        for name, info in mods.items():
            if not info["classes"] and not info["functions"]:
                continue
            print(f"### `{mod}.{name}`\n")
            for cname, bases, doc, methods in info["classes"]:
                b = f"({', '.join(bases)})" if bases else ""
                print(f"- **class `{cname}`{b}**: {doc}")
                if methods:
                    shown = ", ".join(f"`{m}`" for m in methods[:14])
                    more = f" (+{len(methods) - 14} more)" if len(methods) > 14 else ""
                    print(f"  - methods: {shown}{more}")
            for fn, doc in info["functions"]:
                print(f"- `{fn}`: {doc}")
            print()


main()
```
