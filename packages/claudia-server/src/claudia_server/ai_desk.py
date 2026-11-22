"""Who may answer ``@ai``: the providers of this server, and what went wrong with them last (E7.11, D264, D266).

The administrator's page chooses *one* provider for the server. That is not yet the answer for a question: Claude
answers only where the administrator approved *and* the document's owners allowed it (D264), and where it does not, the
server's own provider does and the chat says so. ``ProviderDesk`` is the one place that knows all of that.

The desk is what the settings page changes while the server runs (``AiRuntime.apply``) and what every document's
router asks for every question (``AiRouter``), so a document that was already open when the administrator changed
something follows the change (X1).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from claudia_ai import FailureReason, ModelRunner
from claudia_core import Via

from .ai_consent import CLAUDE, AiConsent

STAND_IN = "stand-in"
LOCAL = "local"
SCRIPTED = Via(STAND_IN, "Scripted stand-in", False)
CLAUDE_VIA = Via(CLAUDE, "Claude", True)

NOTE_NOT_ALLOWED = "Claude is not allowed in this document. The owners can change that in Preferences ▸ AI…"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class Failure:
    """The last time a provider did not answer, for the AI page."""

    provider: str
    reason: FailureReason
    detail: str
    when: str


class ProviderHealth:
    """What went wrong with a provider last. In memory: a restart forgets it, the page shows what is true now."""

    def __init__(self) -> None:
        self.last: Failure | None = None

    def failed(self, failure: Failure) -> None:
        """Note that ``failure.provider`` did not answer."""
        self.last = failure

    def answered(self, provider: str) -> None:
        """Note that ``provider`` answered: what it did wrong before is no longer true."""
        if self.last is not None and self.last.provider == provider:
            self.last = None


@dataclass(frozen=True)
class Decision:
    """Who answers one question: a runner of a language model, or the scripted stand-in (``runner`` is ``None``)."""

    runner: ModelRunner | None
    via: Via


class ProviderDesk:
    """The providers a server has, which one it is set to, and whether Claude may be asked at all."""

    def __init__(self, clock: Callable[[], str] = _now):
        self.provider = STAND_IN
        self.local: ModelRunner | None = None
        self.claude: ModelRunner | None = None
        self.approved = False
        self.health = ProviderHealth()
        self.now = clock

    def install(
        self,
        *,
        provider: str,
        local: ModelRunner | None = None,
        claude: ModelRunner | None = None,
        approved: bool = False,
    ) -> tuple[ModelRunner, ...]:
        """From now on answer as ``provider`` says, with these runners. Returns the runners this replaced, for the
        caller to close (it can take a while, so it is not done here); a question that is running on one of them
        stops (``AiRouter``)."""
        kept = {id(runner) for runner in (local, claude) if runner is not None}
        replaced = tuple(r for r in (self.local, self.claude) if r is not None and id(r) not in kept)
        self.provider, self.local, self.claude, self.approved = provider, local, claude, approved
        return replaced

    def decide(self, consent: AiConsent) -> tuple[Decision, str]:
        """Who answers a question in a document whose owners decided ``consent``, and the sentence for the chat that
        goes with it (``""``: none)."""
        if self.provider == CLAUDE and self.claude is not None and self.approved:
            if consent.allowed(CLAUDE):
                return Decision(self.claude, CLAUDE_VIA), ""
            return self._own(), NOTE_NOT_ALLOWED
        if self.provider == STAND_IN:
            return Decision(None, SCRIPTED), ""
        return self._own(), ""

    def _own(self) -> Decision:
        """The provider of this computer: the local model, or when there is none the stand-in."""
        if self.local is None:
            return Decision(None, SCRIPTED)
        return Decision(self.local, Via(LOCAL, self.local.name, False))

    @property
    def offers_claude(self) -> bool:
        """Has the administrator set Claude up here, with the sentence confirmed? Then the owners of a document may
        allow it; otherwise there is nothing for them to decide."""
        return self.provider == CLAUDE and self.claude is not None and self.approved

    def answering_now(self) -> Via:
        """What the administrator's page says answers ``@ai`` on this server (before the owners of a document have a
        say): the chosen provider, by the name the page shows."""
        if self.offers_claude:
            return Via(CLAUDE, self.claude.name, True)
        return self._own().via

    def may_ask_claude(self, runner: ModelRunner, consent: AiConsent) -> bool:
        """Is ``runner`` still the one Claude is asked through, and do the owners still allow it? A running question
        asks before each of its steps."""
        return runner is self.claude and self.approved and self.provider == CLAUDE and consent.allowed(CLAUDE)

    def close(self) -> None:
        """Stop both runners (the server is stopping)."""
        for runner in (self.local, self.claude):
            if runner is not None:
                runner.close()
