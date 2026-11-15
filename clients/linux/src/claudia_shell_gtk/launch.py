"""Putting the local server together for an app's window, or saying plainly what is missing. No GTK in here.

Since D445 it is one server for the three apps, found or started by ``desktop_server``; this module checks what it
needs, makes its folders and hands over a :class:`~claudia_shell_gtk.desktop_server.DesktopServer` that has not been
asked for yet.

A shell needs two things from outside itself: the Python 3.14 that runs the server and the built web frontend. Both
are looked up (``paths``, ``server``); if one is missing the person gets a message that names it and the way to fix it,
instead of an empty window.
"""

from __future__ import annotations

import os
from pathlib import Path

from .desktop_server import DesktopServer
from .i18n import translate as _
from .identity import AppIdentity
from .paths import find_frontend, server_documents_dir, server_state_dir
from .server import find_server_python

__all__ = ["SetupProblem", "prepare_server"]


class SetupProblem(RuntimeError):
    """Something the shell needs is not there. The message is written for the person who starts the app."""


def prepare_server(identity: AppIdentity, *, repo: Path | None = None) -> DesktopServer:
    """The shared local server for ``identity``'s window, not asked for yet."""
    python = find_server_python(repo=repo)
    if python is None:
        raise SetupProblem(
            _(
                "Claudia's server needs Python 3.14, and none was found.\n"
                "Set CLAUDIA_SERVER_PYTHON to the interpreter of an environment where Claudia is installed "
                "(in a checkout: run 'uv sync' and the interpreter is .venv/bin/python)."
            )
        )
    web = find_frontend(repo=repo)
    if web is None:
        wrong = os.environ.get("CLAUDIA_WEB_DIR")
        if wrong:
            raise SetupProblem(
                _("CLAUDIA_WEB_DIR is set to {wrong}, but there is no built frontend (index.html) in it.").format(
                    wrong=wrong
                )
            )
        raise SetupProblem(
            _(
                "The web frontend has not been built.\n"
                "Build it ('npm run build' in the web folder) or set CLAUDIA_WEB_DIR to a folder that holds it."
            )
        )
    documents = server_documents_dir()
    documents.mkdir(parents=True, exist_ok=True)
    state = server_state_dir()
    state.mkdir(parents=True, exist_ok=True)
    return DesktopServer(app=identity.name, python=python, web=web, documents=documents, state=state)
