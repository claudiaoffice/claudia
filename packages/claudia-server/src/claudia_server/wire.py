"""Small things every app's methods need on the wire: a fresh id, the revision, and "do this, say where we are now".

They were written once per app before (CODE-27); an app's methods import them from here."""

from __future__ import annotations

import secrets
from collections.abc import Container

from .protocol import Context


def fresh_id(prefix: str, taken: Container[str]) -> str:
    """An id nobody has used in this document, ``prefix`` and eight hex digits. Ids are random, never counted: the id of
    a removed object must not come back, or undoing its removal would collide with the newcomer."""
    while True:
        candidate = f"{prefix}{secrets.token_hex(4)}"
        if candidate not in taken:
            return candidate


def current_revision(ctx: Context) -> str | None:
    """The document's revision as the wire writes it; ``None`` for a document nobody has changed yet."""
    revision = ctx.document.revision
    return None if revision is None else revision.to_data()


def done(ctx: Context, command, base, **extra) -> dict:
    """Run ``command`` as the request's author against ``base`` and answer ``extra`` with the new revision."""
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {**extra, "revision": applied.revision.to_data()}


__all__ = ["current_revision", "done", "fresh_id"]
