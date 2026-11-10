"""Locale detection and gettext wiring for the shell (E5.7, D31).

A person's locale is always a client setting — there is no account profile to keep it on, since a document's users
are scoped to that document (D35). This module works out a reasonable default the way gettext-based Linux software
usually does, from the environment the shell runs in, installs a translation so that process-wide ``_()`` works, and
also keeps its own handle on the currently-installed one (:func:`translate`) for callers — ``manifest.py``'s
``menu_xml``, chiefly — that take an explicit function rather than reach for a builtin, so they stay testable with
no locale installed at all. ``fallback=True`` makes every call here safe before any catalog exists for a locale, or
before ``po/`` has catalogs at all: :func:`translate` is then the identity, never an error.

Nothing here imports GTK, so it is tested without a display.
"""

from __future__ import annotations

import gettext
import os
import re
from collections.abc import Callable, Mapping, Sequence
from importlib import resources

__all__ = [
    "DEFAULT_LOCALE",
    "DOMAIN",
    "detect_system_locale",
    "install_translation",
    "negotiate",
    "translate",
]

DOMAIN = "claudia"
DEFAULT_LOCALE = "en"


def _identity(text: str) -> str:
    return text


_active: Callable[[str], str] = _identity  # replaced wholesale by install_translation, below

_TAG = re.compile(r"[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*")
_ENV_VARS = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")  # gettext's own precedence order


def _to_tag(value: str) -> str | None:
    """``"de_DE.UTF-8@euro"`` -> ``"de-DE"``; ``""``, ``"C"`` and ``"POSIX"`` (gettext's "no preference") become
    ``None``."""
    if not value or value in ("C", "POSIX"):
        return None
    bare = value.split(".", 1)[0].split("@", 1)[0].replace("_", "-")
    return bare if _TAG.fullmatch(bare) else None


def detect_system_locale(env: Mapping[str, str] | None = None) -> str:
    """The locale this computer is set to, the way gettext itself picks one (``gettext.find``'s own order): the
    first of ``LANGUAGE``, ``LC_ALL``, ``LC_MESSAGES``, ``LANG`` that is set and usable, normalized to a bare tag.
    ``DEFAULT_LOCALE`` if none is usable. Pass ``env`` (a plain mapping) in a test instead of touching the real
    environment."""
    source: Mapping[str, str] = os.environ if env is None else env
    for name in _ENV_VARS:
        for candidate in source.get(name, "").split(":"):  # LANGUAGE may list several, most preferred first
            tag = _to_tag(candidate)
            if tag:
                return tag
    return DEFAULT_LOCALE


def negotiate(requested: str, available: Sequence[str]) -> str:
    """The best of ``available`` for ``requested``: an exact match, else the same language ignoring region, else
    ``DEFAULT_LOCALE``. ``available`` need not list ``DEFAULT_LOCALE`` — the source text always is it."""
    if requested in available:
        return requested
    base = requested.split("-", 1)[0]
    for candidate in available:
        if candidate.split("-", 1)[0] == base:
            return candidate
    return DEFAULT_LOCALE


def bundled_localedir() -> str:
    """Where this package ships its compiled catalogs: ``locale/<tag>/LC_MESSAGES/claudia.mo``, built from
    ``po/<tag>.po`` by ``scripts/compile_mo.py`` and checked in next to this module exactly like ``data/style.css``
    (D160's reasoning — no system ``msgfmt`` dependency, pure Python, portable)."""
    return str(resources.files("claudia_shell_gtk").joinpath("locale"))


def install_translation(locale: str, localedir: str | None = None) -> Callable[[str], str]:
    """Bind ``_()`` for ``locale`` (process-wide, the usual gettext pattern), remember it as :func:`translate`'s
    answer from now on, and return it too. ``localedir`` defaults to :func:`bundled_localedir`; pass one explicitly
    in a test instead of relying on what happens to be installed next to this module.

    ``fallback=True`` makes this safe before any catalog exists for ``locale``, or before ``po/`` has catalogs at
    all: the installed function is then the identity, never an error."""
    global _active  # noqa: PLW0603 (the one deliberate mutation point for translate()'s module-level state, above)
    translation = gettext.translation(
        DOMAIN, localedir=localedir or bundled_localedir(), languages=[locale, DEFAULT_LOCALE], fallback=True
    )
    translation.install()
    _active = translation.gettext
    return _active


def translate(text: str) -> str:
    """The currently installed translation for ``text`` — read fresh on every call, not captured once, so a later
    :func:`install_translation` call (a language switch, mid-process) changes what this returns without anyone
    needing to re-import it. The identity function until the first :func:`install_translation` call, which is what
    every test in this module (and most of ``test_manifest.py``) gets by just not calling it."""
    return _active(text)
