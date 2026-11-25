"""The server's own messages in the language of the person who gets them (E5.7, D31, D322).

A message is written once, in English, where it is raised: ``msg("{what}: at most {limit} cells at a time",
what=what, limit=limit)``. It reads as that English text everywhere (a log, a test, a client that does not translate),
and it remembers its template and parameters, so that the place that knows the language (the connection, D31: the
language is always the client's own setting) can say it in German with :func:`localized`.

``claudia_core`` and the document packages stay free of catalogs: what they raise reaches a client in English until it
carries a template of its own (backlog E5.17). The catalogs are ``po/<language>.po`` compiled to
``locale/<language>/LC_MESSAGES/claudia.mo`` next to this module (``scripts/compile_mo.py``, checked by the technical
debt check), the same way the Linux shell carries its own.
"""

from __future__ import annotations

import gettext
from functools import cache
from importlib import resources
from typing import Any

from claudia_core import Refusal

DOMAIN = "claudia"
DEFAULT_LOCALE = "en"


class Message(str):
    """English text that can be said in another language: reads as the formatted English, keeps template and
    parameters. Build one with :func:`msg`."""

    template: str
    params: dict[str, Any]

    def __new__(cls, template: str, params: dict[str, Any]) -> Message:
        text = template.format(**params) if params else template
        message = super().__new__(cls, text)
        message.template = template
        message.params = params
        return message


def msg(template: str, **params: Any) -> Message:
    """A message of the server: ``template`` is the English source text (and the key of its translations), with
    ``{name}`` for each of the ``params``. A template without parameters is used as it stands, so braces in it need
    no doubling."""
    return Message(template, params)


def message_of(error: BaseException) -> str:
    """What ``error`` says, as a message that :func:`localized` can say in another language: the template of a
    :class:`~claudia_core.Refusal` of a model (CODE-78, D1510), the message an error of the server's own was raised
    with, anything else as its English text."""
    if isinstance(error, Refusal):
        return Message(error.template, error.params)
    if error.args and isinstance(error.args[0], Message):
        return error.args[0]  # a ValueError of the server's own, raised with a msg(...) (CODE-92)
    return str(error)


def available_locales() -> tuple[str, ...]:
    """The languages with a catalog, besides English, which is the source text."""
    root = resources.files("claudia_server").joinpath("locale")
    return tuple(sorted(entry.name for entry in root.iterdir() if entry.is_dir())) if root.is_dir() else ()


def _language_of(locale: str) -> str | None:
    """The catalog that serves ``locale``: itself, else its language without region, else none (English)."""
    available = available_locales()
    if locale in available:
        return locale
    base = locale.split("-", 1)[0]
    return base if base in available else None


@cache
def _catalog(language: str) -> gettext.NullTranslations:
    localedir = str(resources.files("claudia_server").joinpath("locale"))
    return gettext.translation(DOMAIN, localedir=localedir, languages=[language], fallback=True)


def translate(text: str, locale: str) -> str:
    """``text`` in ``locale`` by the catalog, where it has a translation, else as it is. For a text that is data of a
    package (a function's description) and so has no :class:`Message` of its own (E13.8), and for the template of a
    :class:`Message` (:func:`localized`)."""
    language = _language_of(locale)
    return text if language is None else _catalog(language).gettext(text)


def localized(text: str, locale: str) -> str:
    """``text`` in ``locale``: a :class:`Message` is translated and filled in (a parameter that is a message too, as the
    refusal in "{method}: {reason}" is, is said in ``locale`` as well), anything else is returned as it is. A
    translation whose placeholders do not fit the parameters is never an error: the English text is said instead."""
    if not isinstance(text, Message):
        return text
    translated = translate(text.template, locale)
    if not text.params:
        return translated
    params = {
        key: localized(value, locale) if isinstance(value, Message) else value for key, value in text.params.items()
    }
    try:
        return translated.format(**params)
    except (KeyError, IndexError, ValueError):
        return text.template.format(**params)
