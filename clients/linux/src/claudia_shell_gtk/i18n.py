"""Locale detection and gettext wiring for the shell (E5.7, D31): groundwork, nothing is translated with it yet.

A person's locale is always a client setting — there is no account profile to keep it on, since a document's users
are scoped to that document (D35). This module works out a reasonable default the way gettext-based Linux software
usually does, from the environment the shell runs in, and installs a translation so that ``_()`` works everywhere in
the shell once strings are moved to it (manifest.py already marks GMenu labels translatable, E5.7). Until catalogs
exist (``po/*.mo``), ``install_translation`` is the identity function: ``gettext.translation(..., fallback=True)``
guarantees that, so wiring this in now changes nothing the person sees.

Nothing here imports GTK, so it is tested without a display.
"""

from __future__ import annotations

import gettext
import os
import re
from collections.abc import Callable, Mapping, Sequence

__all__ = ["DEFAULT_LOCALE", "DOMAIN", "detect_system_locale", "install_translation", "negotiate"]

DOMAIN = "claudia"
DEFAULT_LOCALE = "en"

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


def install_translation(locale: str, localedir: str | None = None) -> Callable[[str], str]:
    """Bind ``_()`` for ``locale`` (process-wide, the usual gettext pattern) and return it too.

    ``fallback=True`` makes this safe before any catalog exists for ``locale``, or before ``po/`` has catalogs at
    all: the returned function is then the identity, never an error."""
    translation = gettext.translation(DOMAIN, localedir=localedir, languages=[locale, DEFAULT_LOCALE], fallback=True)
    translation.install()
    return translation.gettext
