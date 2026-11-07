"""Signed-in administrators: bearer tokens, in memory only, lazily expired."""

from claudia_server.admin_sessions import AdminSessions


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_a_fresh_token_resolves_to_the_administrator_that_issued_it():
    sessions = AdminSessions()
    token = sessions.issue("tobi")
    assert sessions.resolve(token) == "tobi"
    assert len(sessions) == 1


def test_an_unknown_or_malformed_token_resolves_to_nothing():
    sessions = AdminSessions()
    assert sessions.resolve("no-such-token") is None
    assert sessions.resolve(None) is None
    assert sessions.resolve(12345) is None


def test_a_session_expires_after_its_lifetime_and_is_forgotten():
    clock = FakeClock()
    sessions = AdminSessions(lifetime=100.0, clock=clock)
    token = sessions.issue("tobi")
    clock.now = 99.0
    assert sessions.resolve(token) == "tobi"
    clock.now = 100.0
    assert sessions.resolve(token) is None
    assert len(sessions) == 0  # forgotten the moment it was looked up, not left lingering


def test_revoking_a_token_signs_it_out_at_once():
    sessions = AdminSessions()
    token = sessions.issue("tobi")
    sessions.revoke(token)
    assert sessions.resolve(token) is None
    sessions.revoke("already gone")  # not an error
    sessions.revoke(None)  # not an error


def test_revoke_all_of_ends_only_that_administrators_sessions():
    sessions = AdminSessions()
    tobi_a, tobi_b, anna = sessions.issue("tobi"), sessions.issue("tobi"), sessions.issue("anna")
    sessions.revoke_all_of("tobi")
    assert sessions.resolve(tobi_a) is None
    assert sessions.resolve(tobi_b) is None
    assert sessions.resolve(anna) == "anna"


def test_each_issued_token_is_different():
    sessions = AdminSessions()
    tokens = {sessions.issue("tobi") for _ in range(20)}
    assert len(tokens) == 20
