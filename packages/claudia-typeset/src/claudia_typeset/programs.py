"""Finding the programs of the person's own LaTeX installation (D90).

Installing LaTeX is the user's job; Claudia only has to be told where it is, and to say clearly what is
wrong when it cannot be found. A setting may be a full path to the program, the folder it lives in (the
``bin`` folder of a TeX Live or MiKTeX installation), or a program name that is looked up on the PATH.
"""

import os
import sys
from pathlib import Path

#: The names of the settings, as a person enters them.
SETTINGS = ("xelatex", "pdftocairo")

#: The help topic that explains how to install LaTeX and set these up.
HELP_TOPIC = "typeset.configure-latex"


class EngineUnavailable(RuntimeError):
    """A program the typesetter needs is not installed, not found or does not run; the message says what to do."""


def _extensions() -> list[str]:
    if sys.platform != "win32":
        return [""]
    return [".exe", *(ext.lower() for ext in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if ext)]


def _runnable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _find(directory: Path, name: str) -> Path | None:
    """The program ``name`` in ``directory`` only (never the working folder), with Windows' usual extensions."""
    for extension in _extensions():
        candidate = directory / (name + extension)
        if _runnable(candidate):
            return Path(os.path.abspath(candidate))  # not resolved: a link's name can decide what a program does
    return None


def _search_path(name: str) -> Path | None:
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if entry and (found := _find(Path(entry), name)):
            return found
    return None


def _hint(setting: str) -> str:
    return (
        f" Install LaTeX and set '{setting}' to the program or to the folder it is in, "
        f"or put that folder on the PATH (help topic: {HELP_TOPIC})."
    )


def resolve_program(
    setting: str, configured: str | os.PathLike[str] | None, default: str, *, hint: str | None = None
) -> Path:
    """The program for ``setting``: what was configured, or ``default`` found on the PATH.

    Raises `EngineUnavailable` with a message that names the setting, the value and what to do. ``hint`` replaces the
    sentence about installing LaTeX, for a caller that resolves another program (it should start with a space).
    """
    advice = _hint(setting) if hint is None else hint
    if configured is None or str(configured) == "":
        found = _search_path(default)
        if found is None:
            raise EngineUnavailable(f"{default} was not found on the PATH of this server." + advice)
        return found
    text = str(configured)
    path = Path(configured)
    names_a_place = os.sep in text or bool(os.altsep and os.altsep in text) or path.is_absolute()
    if not names_a_place:  # a bare program name, never a folder or file of the working directory
        found = _search_path(text)
        if found is None:
            raise EngineUnavailable(f"{text!r} (setting '{setting}') was not found on the PATH." + advice)
        return found
    if path.is_dir():
        found = _find(path, default)
        if found is None:
            raise EngineUnavailable(f"The folder {text!r} (setting '{setting}') has no {default} in it." + advice)
        return found
    # The given path itself, before trying any extension: on Windows, `_extensions()` is PATHEXT (never ""),
    # so a path that already names a runnable file (e.g. ending in its own ".cmd") would otherwise never be
    # tried as-is, and only ever checked with another extension tacked onto the end.
    for candidate in (path, *(Path(text + extension) for extension in _extensions())):
        if candidate.is_file():
            if not _runnable(candidate):
                raise EngineUnavailable(f"{str(candidate)!r} (setting '{setting}') cannot be run.")
            return Path(os.path.abspath(candidate))
    raise EngineUnavailable(f"{text!r} (setting '{setting}') does not exist." + advice)
