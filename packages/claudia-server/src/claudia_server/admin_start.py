"""What happens to a server's administrators before it listens (SEC-12): a reset, naming the first one, the setup code.

:func:`prepare_administrators` runs once, from ``cli.py``, after the state is loaded and before the app exists, so no
request ever meets a half-reset server. In this order:

1. ``--reset-administrators`` (D1375) forgets the administrators. ``admins.json`` is moved aside, not deleted, so a
   mistaken reset can be undone by hand while the server is stopped; ``admin/reset.json`` keeps when and whom, for
   the note on the Administrators page. Settings, fonts and documents are not touched: whoever can start the server
   can read them anyway, and nothing would be protected by throwing them away.
2. ``--admin NAME`` with a password file (D1376) names the first administrator if there is none. It never changes an
   administrator who exists: signing in and *Change password* are for that.
3. If there is still nobody, a setup code is made, written to the state folder and said in the banner (D1371, D1372).
   Otherwise an old code file goes.

Everything that can be refused (the password file, the name) is checked before anything changes."""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .admin import AdminDirectory
from .server_settings import ADMINS_FILE, admin_dir, save_admins
from .setup_code import SetupCode, code_path, remove_code, write_code
from .state import private_dir, write_private

RESET_FILE = "reset.json"
SET_ASIDE = "admins-before-reset-{stamp}.json"


@dataclass(frozen=True)
class ResetNote:
    """When the administrators were last reset from the console, and who they were (D1375)."""

    at: str
    """ISO 8601 UTC."""
    previous: tuple[str, ...]

    def to_data(self) -> dict:
        return {"at": self.at, "previous": list(self.previous)}

    @classmethod
    def from_data(cls, data: dict) -> ResetNote:
        return cls(str(data["at"]), tuple(str(name) for name in data["previous"]))


def load_reset_note(state_dir: Path) -> ResetNote | None:
    """The note of the last reset, until an administrator dismisses it; ``None`` if there is none (or it is damaged)."""
    try:
        return ResetNote.from_data(json.loads((admin_dir(state_dir) / RESET_FILE).read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def dismiss_reset_note(state_dir: Path) -> None:
    """Forget the note (an administrator read it). Dismissing twice is no error."""
    with contextlib.suppress(FileNotFoundError):
        (admin_dir(state_dir) / RESET_FILE).unlink()


@dataclass(frozen=True)
class AdminOptions:
    """The start options about administrators: ``--reset-administrators``, ``--admin``, ``--admin-password-file``."""

    reset: bool = False
    name: str | None = None
    password_file: Path | None = None


@dataclass(frozen=True)
class AdminStart:
    """What :func:`prepare_administrators` did: the code of this run (``None`` once somebody is named), the reset note
    the Administrators page shows, and the lines for the start banner."""

    code: SetupCode | None
    reset: ResetNote | None
    banner: tuple[str, ...]


def read_password_file(path: Path) -> str:
    """The password in ``path``: its first line, without the line end. ``ValueError`` if unreadable or empty."""
    try:
        text = path.expanduser().read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"--admin-password-file: cannot read {path}: {exc}") from exc
    password = text.splitlines()[0] if text else ""
    if not password:
        raise ValueError(f"--admin-password-file: {path} is empty")
    return password


def _set_aside(state_dir: Path, now: str) -> Path | None:
    """Move ``admins.json`` aside, next to where it was; the new name, or ``None`` if there was no file."""
    folder = admin_dir(state_dir)
    source = folder / ADMINS_FILE
    if not source.is_file():
        return None
    stamp = now.replace(":", "-")
    target = folder / SET_ASIDE.format(stamp=stamp)
    n = 1
    while target.exists():
        n += 1
        target = folder / SET_ASIDE.format(stamp=f"{stamp}-{n}")
    os.replace(source, target)
    return target


def _reset(state_dir: Path, admins: AdminDirectory, now: str) -> tuple[ResetNote | None, str]:
    previous = tuple(account.name for account in admins.list_admins())
    aside = _set_aside(state_dir, now)
    admins.clear()
    if not previous:
        return None, "administrators reset: there were none"
    note = ResetNote(now, previous)
    private_dir(admin_dir(state_dir))
    write_private(admin_dir(state_dir) / RESET_FILE, json.dumps(note.to_data()).encode("utf-8"))
    kept = f" (kept aside as {aside.name})" if aside is not None else ""
    return note, f"administrators reset: {', '.join(previous)} removed{kept}; settings unchanged"


def _code_lines(state_dir: Path, code: SetupCode, link_base: str | None) -> list[str]:
    lines = [
        "no administrator yet: name one with this setup code, which works until one is named or the server stops",
        f"  setup code   {code}",
    ]
    if link_base is not None:
        lines.append(f"  or open      {link_base}#setup={code}")
    lines.append(f"  also in      {code_path(state_dir)} (this user only)")
    return lines


def prepare_administrators(
    state_dir: Path, admins: AdminDirectory, options: AdminOptions, *, link_base: str | None, now: str
) -> AdminStart:
    """Reset, name and make a code as the module docstring says. ``admins`` is changed in place and saved.

    ``link_base`` is the address of the settings pages for the banner's link (``None`` without the web app);
    ``ValueError`` (before anything changes) for a password file or a name that cannot be used."""
    password = None
    if options.name is not None:
        if options.password_file is None:
            raise ValueError("--admin needs --admin-password-file (or CLAUDIA_ADMIN_PASSWORD_FILE)")
        password = read_password_file(options.password_file)
        admins.check_new(options.name, password)

    banner: list[str] = []
    note = load_reset_note(state_dir)
    if options.reset:
        reset, line = _reset(state_dir, admins, now)
        note = reset or note
        banner.append(line)

    ignored = False
    if options.name is not None and password is not None:
        ignored = bool(admins)
        if not ignored:
            admins.add(options.name, password, added=now)
            save_admins(state_dir, admins)

    if admins:
        remove_code(state_dir)
        names = ", ".join(a.name for a in admins.list_admins())
        named = " (named at start with --admin)" if options.name is not None and not ignored else ""
        banner.append(f"administrators: {names}{named}")
        if ignored:
            banner.append(f"--admin {options.name} changed nothing: this server has administrators")
        return AdminStart(None, note, tuple(banner))

    code = SetupCode.make()
    write_code(state_dir, code)
    banner += _code_lines(state_dir, code, link_base)
    return AdminStart(code, note, tuple(banner))
