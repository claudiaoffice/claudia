"""Putting a local server together for an app, or saying plainly what is missing. No GTK in here.

A shell needs two things from outside itself: the Python 3.14 that runs the server and the built web frontend. Both
are looked up (``paths``, ``server``); if one is missing the person gets a message that names it and the way to fix it,
instead of an empty window.
"""

from __future__ import annotations

import os
from pathlib import Path

from .identity import AppIdentity
from .paths import documents_dir, find_frontend, state_dir
from .server import LOOPBACK, LocalServer, composes_command, find_server_python, free_port

__all__ = ["SetupProblem", "prepare_server"]


class SetupProblem(RuntimeError):
    """Something the shell needs is not there. The message is written for the person who starts the app."""


def prepare_server(identity: AppIdentity, *, repo: Path | None = None) -> LocalServer:
    """A :class:`~claudia_shell_gtk.server.LocalServer` for ``identity``, not started yet."""
    python = find_server_python(repo=repo)
    if python is None:
        raise SetupProblem(
            "Claudia's server needs Python 3.14, and none was found.\n"
            "Set CLAUDIA_SERVER_PYTHON to the interpreter of an environment where Claudia is installed "
            "(in a checkout: run 'uv sync' and the interpreter is .venv/bin/python)."
        )
    web = find_frontend(repo=repo)
    if web is None:
        wrong = os.environ.get("CLAUDIA_WEB_DIR")
        raise SetupProblem(
            f"CLAUDIA_WEB_DIR is set to {wrong}, but there is no built frontend (index.html) in it."
            if wrong
            else "The web frontend has not been built.\n"
            "Build it ('npm run build' in the web folder) or set CLAUDIA_WEB_DIR to a folder that holds it."
        )
    documents = documents_dir(identity.name)
    documents.mkdir(parents=True, exist_ok=True)
    state = state_dir(identity.name)
    state.mkdir(parents=True, exist_ok=True)
    port = free_port()
    command = composes_command(python, port=port, documents=documents, web=web, state=state)
    return LocalServer(command, url=f"http://{LOOPBACK}:{port}", log=state / "server.log")
