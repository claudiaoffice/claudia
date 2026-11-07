"""The restore/switch consent flow over the wire, through a real ``Hub`` and ``HostedDocument`` (E3.7, E3.8).

``test_server_restore.py`` tests ``RestoreCoordinator`` in isolation; this file tests that it is wired into
``hub.py`` and ``protocol.py`` correctly: who gets which event, what a reconnecting client sees in its welcome, and
what connecting or disconnecting during an open vote does. No sockets: a connection is given a ``send`` callable,
same as the rest of the hub tests.
"""

import asyncio
import json

import pytest

from claudia_core.testing import ListModel
from claudia_server.auth import Account
from claudia_server.hub import Hub, MemoryProvider

INSERT = {"k": "list.Insert", "s": 1, "d": {"index": 0, "value": 5}}


class Client:
    """A connected person: everything the server sent is in ``frames``."""

    def __init__(self, hosted, account):
        self.frames: list[dict] = []
        self.connection = hosted.connect(account, lambda text: self.frames.append(json.loads(text)))
        self._next = 0

    def request(self, method, params=None):
        self._next += 1
        self.connection.handle(json.dumps({"id": self._next, "method": method, "params": params}))
        return self.frames[-1]

    def events(self, name):
        return [f["data"] for f in self.frames if f.get("event") == name]

    def forget(self):
        self.frames.clear()

    def close(self):
        self.connection.close()


@pytest.fixture
def provider(clock):
    return MemoryProvider(ListModel, clock=clock.time, lock_clock=clock.lock_time)


@pytest.fixture
def hub(provider, clock):
    return Hub(provider, clock=clock.lock_time)


@pytest.fixture
def hosted(hub):
    return asyncio.run(hub.open("plan", create=True))


@pytest.fixture
def worked(hosted):
    """ana and ben each do something, then ana saves a checkpoint, then each does one more thing."""
    ana, ben = Client(hosted, Account("ana", "owner")), Client(hosted, Account("ben", "editor"))
    ana.request("apply", {"command": INSERT})
    ben.request("apply", {"command": INSERT})
    ana.request("save_checkpoint", {"label": "good"})
    ana.request("apply", {"command": INSERT})
    for c in (ana, ben):
        c.forget()
    return hosted, ana, ben


# ------------------------------------------------------------------------------------------ peek_line
def test_peeking_the_active_line_matches_snapshot(worked):
    hosted, ana, _ = worked
    peeked = ana.request("peek_line", {"line": "main"})["result"]
    snap = ana.request("snapshot")["result"]
    assert peeked["state"] == snap["state"] and peeked["revision"] == snap["revision"]


def test_peeking_an_unknown_line_is_a_command_error(worked):
    _, ana, _ = worked
    error = ana.request("peek_line", {"line": "nowhere"})["error"]
    assert error["code"] == "command_error"


def test_a_viewer_may_peek(hosted):
    vera = Client(hosted, Account("vera", "viewer"))
    assert vera.request("peek_line", {"line": "main"})["ok"]


# ------------------------------------------------------------------------------------------ restore_policy
def test_the_default_policy_is_consensus(hosted):
    ana = Client(hosted, Account("ana", "owner"))
    assert ana.request("restore_policy")["result"] == {"policy": "consensus"}


def test_only_an_owner_sets_the_policy(hosted):
    ana, ben = Client(hosted, Account("ana", "owner")), Client(hosted, Account("ben", "editor"))
    assert ben.request("set_restore_policy", {"policy": "veto"})["error"]["code"] == "forbidden"
    assert ana.request("set_restore_policy", {"policy": "veto"})["result"] == {"policy": "veto"}
    assert ben.request("restore_policy")["result"] == {"policy": "veto"}


def test_an_unknown_policy_is_rejected(hosted):
    ana = Client(hosted, Account("ana", "owner"))
    assert ana.request("set_restore_policy", {"policy": "majority"})["error"]["code"] == "bad_request"


# ------------------------------------------------------------------------------------------ proposing: the lone editor
def test_the_only_editor_gets_no_vote(hosted):
    ana = Client(hosted, Account("ana", "owner"))
    ana.request("apply", {"command": INSERT})
    ana.request("save_checkpoint", {"label": "good"})
    ana.request("apply", {"command": INSERT})
    ana.forget()
    answer = ana.request("propose_restore", {"checkpoint": 1})
    assert answer["result"] == {"applied": True, "proposal": None}
    assert ana.events("branch") and ana.events("rebuilt")  # the kernel's own notice, same as any restore
    assert not ana.events("restore_proposed")


def test_a_viewer_connected_does_not_count_as_an_editor(hosted):
    ana = Client(hosted, Account("ana", "owner"))
    Client(hosted, Account("vera", "viewer"))
    ana.request("apply", {"command": INSERT})
    ana.request("save_checkpoint", {"label": "good"})
    ana.request("apply", {"command": INSERT})
    ana.forget()
    assert ana.request("propose_restore", {"checkpoint": 1})["result"]["applied"] is True


def test_a_viewer_cannot_propose(hosted):
    vera = Client(hosted, Account("vera", "viewer"))
    assert vera.request("propose_restore", {"checkpoint": 1})["error"]["code"] == "forbidden"


# ------------------------------------------------------------------------------------------ proposing: a real vote
def test_two_editors_open_a_proposal_instead(worked):
    hosted, ana, ben = worked
    answer = ana.request("propose_restore", {"checkpoint": 1})["result"]
    assert answer["applied"] is False
    proposal = answer["proposal"]
    assert proposal["kind"] == "restore" and proposal["by"] == "ana" and proposal["checkpoint"] == 1
    assert proposal["group"] == ["ana", "ben"] and proposal["agreed"] == ["ana"]
    assert ben.events("restore_proposed")[-1] == proposal  # ben was told without asking
    assert not ana.events("branch")  # nothing happened to the document yet


def test_only_one_proposal_is_open_at_a_time(worked):
    hosted, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    assert ben.request("propose_restore", {"checkpoint": 1})["error"]["code"] == "command_error"


def test_an_unknown_checkpoint_is_a_command_error(worked):
    _, ana, _ = worked
    assert ana.request("propose_restore", {"checkpoint": 99})["error"]["code"] == "command_error"


def test_propose_switch_suggests_a_line_instead(worked):
    hosted, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    ben.request("answer_restore", {"agree": True})  # forks "restore-1"; "main" is now hidden
    assert hosted.document.branch == "restore-1"
    ana.forget()
    ben.forget()
    answer = ana.request("propose_switch", {"line": "main"})["result"]
    assert answer["applied"] is False
    assert answer["proposal"]["kind"] == "switch" and answer["proposal"]["line"] == "main"
    assert ben.events("restore_proposed")[-1] == answer["proposal"]


def test_switching_to_an_unknown_line_is_a_command_error(worked):
    _, ana, _ = worked
    assert ana.request("propose_switch", {"line": "nowhere"})["error"]["code"] == "command_error"


def test_the_assistant_may_not_propose_answer_or_withdraw(hosted):
    ai = Client(hosted, Account.assistant())
    assert ai.request("propose_restore", {"checkpoint": 1})["error"]["code"] == "forbidden"
    assert ai.request("propose_switch", {"line": "main"})["error"]["code"] == "forbidden"
    assert ai.request("answer_restore", {"agree": True})["error"]["code"] == "forbidden"
    assert ai.request("withdraw_restore")["error"]["code"] == "forbidden"


# ------------------------------------------------------------------------------------------ answering
def test_everybody_agreeing_carries_it_out(worked):
    hosted, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    ana.forget()
    ben.forget()
    answer = ben.request("answer_restore", {"agree": True})["result"]
    assert answer == {"resolved": "agreed"}
    assert ben.events("restore_resolved")[-1] == {"outcome": "agreed"}
    assert ana.events("restore_resolved")[-1] == {"outcome": "agreed"}  # the proposer hears it too
    assert ana.events("branch") and ana.events("rebuilt")
    assert hosted.document.branch.startswith("restore-")


def test_a_decline_resolves_it_without_changing_the_document(worked):
    hosted, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    before = hosted.document.branch
    ana.forget()
    ben.forget()
    assert ben.request("answer_restore", {"agree": False})["result"] == {"resolved": "declined"}
    assert ana.events("restore_resolved")[-1] == {"outcome": "declined"}
    assert hosted.document.branch == before
    assert not ana.events("branch")


def test_a_vote_that_does_not_resolve_it_still_tells_everybody(hosted):
    ana, ben, cara = (
        Client(hosted, Account("ana", "owner")),
        Client(hosted, Account("ben", "editor")),
        Client(hosted, Account("cara", "editor")),
    )
    for c in (ana, ben, cara):
        c.request("apply", {"command": INSERT})
    ana.request("save_checkpoint", {"label": "good"})
    ana.request("apply", {"command": INSERT})
    ana.request("propose_restore", {"checkpoint": 1})
    for c in (ana, ben, cara):
        c.forget()
    ben.request("answer_restore", {"agree": True})
    tally = cara.events("restore_proposed")[-1]
    assert tally["agreed"] == ["ana", "ben"] and not cara.events("restore_resolved")


def test_answering_with_nothing_open_is_a_command_error(worked):
    _, ana, _ = worked
    assert ana.request("answer_restore", {"agree": True})["error"]["code"] == "command_error"


def test_a_viewer_cannot_answer(worked):
    hosted, ana, _ = worked
    ana.request("propose_restore", {"checkpoint": 1})
    vera = Client(hosted, Account("vera", "viewer"))
    assert vera.request("answer_restore", {"agree": True})["error"]["code"] == "forbidden"


# ------------------------------------------------------------------------------------------ withdrawing
def test_the_proposer_may_withdraw(worked):
    hosted, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    ana.forget()
    ben.forget()
    assert ana.request("withdraw_restore")["result"] == {}
    assert ben.events("restore_resolved")[-1] == {"outcome": "withdrawn"}
    assert ana.request("propose_restore", {"checkpoint": 1})["result"]["applied"] is False  # open again, cleanly


def test_an_editor_who_is_not_the_proposer_cannot_withdraw(worked):
    _, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    assert ben.request("withdraw_restore")["error"]["code"] == "command_error"


def test_an_owner_may_withdraw_somebody_elses_suggestion(hosted):
    ana, ben = Client(hosted, Account("ana", "owner")), Client(hosted, Account("ben", "editor"))
    for c in (ana, ben):
        c.request("apply", {"command": INSERT})
    ben.request("save_checkpoint", {"label": "good"})
    ben.request("apply", {"command": INSERT})
    ben.request("propose_restore", {"checkpoint": 1})
    assert ana.request("withdraw_restore")["result"] == {}


# ------------------------------------------------------------------------------------------ connecting and leaving
def test_a_new_editor_joins_the_group_and_sees_it_in_their_welcome(worked):
    hosted, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    cara = Client(hosted, Account("cara", "editor"))
    assert cara.connection.welcome()["proposal"]["group"] == ["ana", "ben", "cara"]
    cara.forget()
    ana.forget()
    ben.forget()
    cara.request("answer_restore", {"agree": True})
    assert not cara.events("restore_resolved")  # ana and ben have not all answered yet
    ben.request("answer_restore", {"agree": True})
    assert cara.events("restore_resolved")[-1] == {"outcome": "agreed"}


def test_leaving_drops_an_editor_from_the_vote(hosted):
    # a third editor so that ben leaving does not also resolve it (that case has its own test below)
    ana, ben, cara = (
        Client(hosted, Account("ana", "owner")),
        Client(hosted, Account("ben", "editor")),
        Client(hosted, Account("cara", "editor")),
    )
    for c in (ana, ben, cara):
        c.request("apply", {"command": INSERT})
    ana.request("save_checkpoint", {"label": "good"})
    ana.request("apply", {"command": INSERT})
    ana.request("propose_restore", {"checkpoint": 1})
    ben.close()
    proposal = hosted.restore.open_proposal
    assert proposal is not None and proposal.group == {"ana", "cara"} and proposal.agreed == {"ana"}


def test_leaving_the_last_undecided_editor_resolves_it_agreed(worked):
    # with ben gone, everybody left in the group (just ana) has agreed, so it carries out on its own
    hosted, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    ana.forget()
    ben.close()
    assert ana.events("restore_resolved")[-1] == {"outcome": "agreed"}
    assert hosted.document.branch.startswith("restore-")


def test_leaving_can_resolve_it(hosted):
    ana, ben, cara = (
        Client(hosted, Account("ana", "owner")),
        Client(hosted, Account("ben", "editor")),
        Client(hosted, Account("cara", "editor")),
    )
    for c in (ana, ben, cara):
        c.request("apply", {"command": INSERT})
    ana.request("save_checkpoint", {"label": "good"})
    ana.request("apply", {"command": INSERT})
    ana.request("propose_restore", {"checkpoint": 1})
    ben.request("answer_restore", {"agree": True})
    ana.forget()
    cara.close()  # only ana and ben remain, and both agreed
    assert ana.events("restore_resolved")[-1] == {"outcome": "agreed"}


def test_the_proposer_leaving_withdraws_it(worked):
    hosted, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    ben.forget()
    ana.close()
    assert ben.events("restore_resolved")[-1] == {"outcome": "withdrawn"}
    assert hosted.restore.open_proposal is None


# ------------------------------------------------------------------------------------------ the deadline
def test_a_forgotten_vote_resolves_at_the_deadline(worked, clock):
    hosted, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    ana.forget()
    clock.advance(15 * 60.0)
    hosted.sweep()
    assert ana.events("restore_resolved")[-1] == {"outcome": "declined"}  # consensus: silence is not agreement


def test_under_veto_a_forgotten_vote_is_agreed_at_the_deadline(worked, clock):
    hosted, ana, ben = worked
    ana.request("set_restore_policy", {"policy": "veto"})
    ana.request("propose_restore", {"checkpoint": 1})
    ana.forget()
    clock.advance(15 * 60.0)
    hosted.sweep()
    assert ana.events("restore_resolved")[-1] == {"outcome": "agreed"}
    assert ana.events("branch")


# ------------------------------------------------------------------------------------------ welcome: lines, returned
def test_welcome_lists_the_lines(worked):
    _, ana, _ = worked
    welcome = ana.connection.welcome()
    assert welcome["lines"] == [{"name": "main", "head": welcome["revision"], "active": True}]


def test_a_returning_person_is_told_what_happened_while_they_were_away(worked):
    hosted, ana, ben = worked
    ben.close()  # ben leaves on "main"
    ana.request("propose_restore", {"checkpoint": 1})  # ana alone now: applied at once, forking "restore-1"
    ben2 = Client(hosted, Account("ben", "editor"))  # ben comes back
    notice = ben2.connection.welcome()["returned"]
    assert notice == {"by": "ana", "kind": "restore", "label": "checkpoint “good”", "agreed": ["ana"]}
    # delivered once: a second reconnect with nothing new since says nothing
    ben2.close()
    ben3 = Client(hosted, Account("ben", "editor"))
    assert ben3.connection.welcome()["returned"] is None


def test_nobody_is_told_anything_if_nothing_happened_while_they_were_away(worked):
    hosted, ana, ben = worked
    ben.close()
    ben2 = Client(hosted, Account("ben", "editor"))
    assert ben2.connection.welcome()["returned"] is None


# ------------------------------------------------------------------------------------------ discarding hidden lines
def test_an_owner_discards_every_hidden_line(worked):
    hosted, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    ben.request("answer_restore", {"agree": True})  # forks restore-1 at the checkpoint; main:3 becomes hidden
    ana.forget()
    removed = ana.request("discard_side_history")["result"]["discarded"]
    # "main" survives: it still holds the ancestry it shares with restore-1, up to the checkpoint.
    assert removed and hosted.document.side_revisions() == []
    assert {x.name for x in hosted.document.lines()} == {"main", "restore-1"}


def test_only_an_owner_discards(worked):
    _, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    ben.request("answer_restore", {"agree": True})
    assert ben.request("discard_side_history")["error"]["code"] == "forbidden"


def test_discarding_is_refused_while_a_suggestion_is_open(worked):
    hosted, ana, ben = worked
    ana.request("propose_restore", {"checkpoint": 1})
    ben.request("answer_restore", {"agree": True})
    ana.request("propose_switch", {"line": "main"})
    assert ana.request("discard_side_history")["error"]["code"] == "command_error"
    assert hosted.document.side_revisions() != []
