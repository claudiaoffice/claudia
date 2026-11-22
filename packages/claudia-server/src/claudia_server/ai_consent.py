"""The owners' consent to a remote AI provider in one live document (E7.11, D264).

A remote provider (Claude) is asked about a document only when **both** the administrator and the owners agreed: the
administrator when applying the provider in the server settings, the owners here, per document, off by default. This
module is the owners' half: ``AiConsent`` is what the document's list of decisions folds to, and ``ConsentBook`` keeps
it for a hosted document, live, so the gate and the router read the current state and not the state at opening.

The decisions are kept in the document file (``claudia_document_file.ConsentRecord``), sealed so that whoever
administers the server cannot give them. A server that keeps no document files has no place for them: there it is always
*off* (failing safe), and nobody can turn it on.
"""

from __future__ import annotations

from dataclasses import dataclass

from claudia_document_file import ConsentRecord

from .auth import ConsentDirectory

CLAUDE = "claude"
"""The provider the owners' consent is for. Written in the file, so it is not a label to translate."""


@dataclass(frozen=True)
class AiConsent:
    """What the owners decided, oldest decision first. No decision about a provider means *not allowed*."""

    records: tuple[ConsentRecord, ...] = ()

    def latest(self, provider: str) -> ConsentRecord | None:
        """The last decision about ``provider``."""
        return next((r for r in reversed(self.records) if r.provider == provider), None)

    def allowed(self, provider: str) -> bool:
        """May ``provider`` be sent the content of this document?"""
        latest = self.latest(provider)
        return latest is not None and latest.allowed


class ConsentNotKept(Exception):
    """This server keeps no place for the owners' consent (its documents are not files)."""


class ConsentBook:
    """The consent of one hosted document: read from its directory when first needed, and kept up to date here."""

    def __init__(self, directory: object, doc_id: str):
        self._directory = directory
        self._doc_id = doc_id
        self._state: AiConsent | None = None

    @property
    def kept(self) -> bool:
        """Does this server keep the owners' consent at all?"""
        return isinstance(self._directory, ConsentDirectory)

    @property
    def state(self) -> AiConsent:
        """What the owners decided, as it is now. Off when nothing can be read: the document is sealed until somebody
        who holds its keys has opened it, and then not being able to look means not being allowed."""
        if self._state is not None:
            return self._state
        if not isinstance(self._directory, ConsentDirectory):
            return AiConsent()
        try:
            rows = self._directory.consent_rows(self._doc_id)
        except ValueError:  # DocumentSealed: not cached, so that the next question looks again
            return AiConsent()
        self._state = AiConsent(tuple(rows))
        return self._state

    def decide(self, provider: str, allowed: bool, who: str, when: str) -> ConsentRecord | None:
        """Record that ``who`` allowed or withdrew ``provider``; ``None`` (nothing recorded) when it already stands so.
        ``ConsentNotKept`` on a server with no place for it."""
        if not isinstance(self._directory, ConsentDirectory):
            raise ConsentNotKept
        current = self.state
        if current.allowed(provider) == allowed:
            return None
        record = ConsentRecord(provider, allowed, who, when)
        self._directory.record_consent(self._doc_id, record)
        self._state = AiConsent((*current.records, record))
        return record


def consent_view(state: AiConsent, provider: str, owners: list[str]) -> dict:
    """What a window is told: where ``provider`` stands, who decided last and when, who the owners are (the people who
    can change it), and every decision so far."""
    latest = state.latest(provider)
    return {
        "provider": provider,
        "allowed": state.allowed(provider),
        "by": latest.who if latest else None,
        "at": latest.when if latest else None,
        "owners": owners,
        "history": [
            {"allowed": r.allowed, "who": r.who, "when": r.when} for r in state.records if r.provider == provider
        ],
    }
