"""What happens when a person asks a window to connect to a server (E5.8): see connector.py. No GTK, no network."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from claudia_shell_gtk import settings
from claudia_shell_gtk.connection import NeedsTrust, Reached, Refused
from claudia_shell_gtk.connector import Connector, ServerBook, run_threaded
from claudia_shell_gtk.trust import TrustStore
from claudia_shell_gtk.x509 import Certificate

SERVER = "https://demo.example.org:8420"
CERT = Certificate(
    subject="demo.example.org",
    issuer="demo.example.org",
    not_before=datetime(2026, 1, 1, tzinfo=UTC),
    not_after=datetime(2027, 1, 1, tzinfo=UTC),
    names=("demo.example.org",),
    self_signed=True,
    sha256="ab" * 32,
)


class Rig:
    """A connector with a scripted check, a synchronous worker, and recorders for what it does."""

    def __init__(self, tmp_path: Path, outcomes: list) -> None:
        self.path = tmp_path / "shell.json"
        self.book = ServerBook(
            "computes", local_origin="http://127.0.0.1:41233", local_label="This computer", path=self.path
        )
        self.trust = TrustStore(self.path)
        self.switched: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.checks: list[tuple[str, str, dict]] = []
        self.questions: list[tuple[NeedsTrust, object]] = []
        self.outcomes = outcomes
        self.connector = Connector(
            "computes",
            book=self.book,
            trust=self.trust,
            switch=self.switched.append,
            fail=lambda code, message: self.failed.append((code, message)),
            check=self._check,
            work=lambda job, done: done(job()),
        )

    def _check(self, address, app, *, trusted):  # noqa: ANN001, ANN202
        self.checks.append((address.origin, app, dict(trusted)))
        return self.outcomes.pop(0)

    def ask_to_trust(self) -> None:
        self.connector.ask_trust = lambda needs, answer: self.questions.append((needs, answer))


@pytest.fixture
def rig(tmp_path: Path):
    def make(*outcomes):  # noqa: ANN002, ANN202
        return Rig(tmp_path, list(outcomes))

    return make


# ---------------------------------------------------------------------------------------------------- connecting


def test_a_server_that_is_reached_is_shown_and_remembered(rig) -> None:  # noqa: ANN001
    r = rig(Reached(SERVER, "computes"))
    r.connector.connect("demo.example.org:8420")
    assert r.checks == [(SERVER, "computes", {})]
    assert r.switched == [SERVER]
    assert r.failed == []
    assert [e["origin"] for e in settings.load_servers("computes", r.path)] == [SERVER]


def test_the_check_is_for_the_app_of_this_window_always(rig) -> None:  # noqa: ANN001
    r = rig(Reached(SERVER, "computes"))
    r.connector.connect(SERVER)
    assert r.checks[0][1] == "computes"


def test_an_address_that_is_refused_is_reported_without_asking_the_network(rig) -> None:  # noqa: ANN001
    r = rig()
    r.connector.connect("http://192.0.2.7:8420")
    assert r.checks == []
    assert [code for code, _ in r.failed] == ["insecure"]
    assert "https" in r.failed[0][1]
    r.connector.connect("ftp://x")
    assert [code for code, _ in r.failed] == ["insecure", "bad_address"]


def test_a_refusal_of_the_check_is_reported_and_nothing_changes(rig) -> None:  # noqa: ANN001
    r = rig(Refused("wrong_app", "That server runs Claudia Composes."))
    r.connector.connect(SERVER)
    assert r.failed == [("wrong_app", "That server runs Claudia Composes.")]
    assert r.switched == []
    assert settings.load_servers("computes", r.path) == []


def test_the_server_of_this_computer_is_not_written_down(rig) -> None:  # noqa: ANN001
    local = "http://127.0.0.1:41233"
    r = rig(Reached(local, "computes"))
    r.connector.connect(local)
    assert r.switched == [local]
    assert settings.load_servers("computes", r.path) == []


def test_the_pins_are_handed_to_the_check(rig) -> None:  # noqa: ANN001
    r = rig(Reached(SERVER, "computes"))
    r.trust.trust(SERVER, "cd" * 32)
    r.connector.connect(SERVER)
    assert r.checks[0][2][SERVER]["sha256"] == "cd" * 32


# ----------------------------------------------------------------------------------------------------- trusting


def test_without_a_dialog_a_certificate_nobody_vouches_for_is_a_refusal(rig) -> None:  # noqa: ANN001
    r = rig(NeedsTrust(SERVER, "computes", CERT, "unknown_issuer", None))
    r.connector.connect(SERVER)
    assert [code for code, _ in r.failed] == ["certificate_invalid"]
    assert r.switched == []
    assert r.trust.pinned(SERVER) is None  # nothing is trusted unasked


def test_the_person_is_asked_and_trusting_connects(rig) -> None:  # noqa: ANN001
    r = rig(NeedsTrust(SERVER, "computes", CERT, "unknown_issuer", None), Reached(SERVER, "computes", CERT.sha256))
    r.ask_to_trust()
    r.connector.connect(SERVER)
    assert r.switched == [] and r.failed == []  # waiting for the answer
    needs, answer = r.questions[0]
    assert needs.certificate is CERT
    answer(True)
    assert r.trust.pinned(SERVER) == CERT.sha256
    assert len(r.checks) == 2  # checked again, now with the pin: the certificate that is trusted is the one shown
    assert r.checks[1][2][SERVER]["sha256"] == CERT.sha256
    assert r.switched == [SERVER]


def test_declining_connects_nowhere_and_trusts_nothing(rig) -> None:  # noqa: ANN001
    r = rig(NeedsTrust(SERVER, "computes", CERT, "unknown_issuer", None))
    r.ask_to_trust()
    r.connector.connect(SERVER)
    r.questions[0][1](False)
    assert [code for code, _ in r.failed] == ["not_trusted"]
    assert "did not trust" in r.failed[0][1]
    assert r.trust.pinned(SERVER) is None
    assert r.switched == []


def test_an_answer_counts_once(rig) -> None:  # noqa: ANN001
    r = rig(NeedsTrust(SERVER, "computes", CERT, "unknown_issuer", None), Reached(SERVER, "computes"))
    r.ask_to_trust()
    r.connector.connect(SERVER)
    answer = r.questions[0][1]
    answer(True)
    answer(True)
    answer(False)
    assert r.switched == [SERVER]
    assert r.failed == []


def test_a_certificate_that_changes_again_while_asking_is_not_asked_about_a_second_time(rig) -> None:  # noqa: ANN001
    other = NeedsTrust(SERVER, "computes", CERT, "unknown_issuer", CERT.sha256)
    r = rig(NeedsTrust(SERVER, "computes", CERT, "unknown_issuer", None), other)
    r.ask_to_trust()
    r.connector.connect(SERVER)
    r.questions[0][1](True)
    assert len(r.questions) == 1
    assert [code for code, _ in r.failed] == ["certificate_invalid"]


def test_the_question_for_a_changed_certificate_carries_the_old_fingerprint(rig) -> None:  # noqa: ANN001
    r = rig(NeedsTrust(SERVER, "computes", CERT, "unknown_issuer", "ef" * 32))
    r.ask_to_trust()
    r.connector.connect(SERVER)
    assert r.questions[0][0].previous == "ef" * 32


# ------------------------------------------------------------------------------------------------- latest wins


def test_a_newer_request_replaces_an_older_one_that_is_still_running(tmp_path: Path) -> None:
    pending: list = []
    path = tmp_path / "shell.json"
    switched: list[str] = []
    answers = iter([Reached("https://a.example.org", "computes"), Reached("https://b.example.org", "computes")])
    connector = Connector(
        "computes",
        book=ServerBook("computes", local_origin=None, local_label="x", path=path),
        trust=TrustStore(path),
        switch=switched.append,
        fail=lambda *_: None,
        check=lambda address, app, *, trusted: next(answers),
        work=lambda job, done: pending.append((job, done)),
    )
    connector.connect("a.example.org")
    connector.connect("b.example.org")
    for job, done in pending:  # the first finishes last
        done(job())
    assert switched == ["https://b.example.org"]


# ------------------------------------------------------------------------------------------------ the server list


def test_the_page_gets_this_computer_first(tmp_path: Path) -> None:
    path = tmp_path / "shell.json"
    settings.save_servers("computes", [{"origin": SERVER, "label": "Demo", "custom": True}], path)
    book = ServerBook("computes", local_origin="http://127.0.0.1:41233", local_label="This computer", path=path)
    shown = book.entries()
    assert [(e["origin"], e.get("local")) for e in shown] == [("http://127.0.0.1:41233", True), (SERVER, None)]


def test_without_a_local_server_this_computer_is_not_listed(tmp_path: Path) -> None:
    book = ServerBook("computes", local_origin=None, local_label="This computer", path=tmp_path / "shell.json")
    assert book.entries() == []


def test_the_local_server_can_be_set_when_it_has_started(tmp_path: Path) -> None:
    book = ServerBook("computes", local_origin=None, local_label="This computer", path=tmp_path / "shell.json")
    book.local_origin = "http://127.0.0.1:5"
    assert book.entries()[0]["origin"] == "http://127.0.0.1:5"


def test_a_list_from_the_page_is_cleaned_and_kept_per_app(tmp_path: Path) -> None:
    path = tmp_path / "shell.json"
    book = ServerBook("computes", local_origin="http://127.0.0.1:41233", local_label="This computer", path=path)
    book.replace(
        [
            {"origin": "http://127.0.0.1:41233", "label": "This computer", "custom": True, "local": True},
            {"origin": SERVER, "label": "Demo", "custom": True},
            {"origin": "javascript:1", "label": "x", "custom": False},
        ]
    )
    assert settings.load_servers("computes", path) == [{"origin": SERVER, "label": "Demo", "custom": True}]
    assert settings.load_servers("creates", path) == []


def test_a_server_removed_by_the_page_is_gone(tmp_path: Path) -> None:
    path = tmp_path / "shell.json"
    book = ServerBook("computes", local_origin=None, local_label="x", path=path)
    book.remember(SERVER)
    book.replace([])
    assert book.entries() == []


# -------------------------------------------------------------------------------------------------- the thread


def test_the_real_worker_runs_the_job_off_the_calling_thread_and_delivers_on_the_given_one() -> None:
    import threading

    delivered: list[tuple[int, str]] = []
    finished = threading.Event()
    caller = threading.get_ident()
    jobs: list[int] = []

    def deliver(call) -> None:  # noqa: ANN001
        call()

    work = run_threaded(deliver)

    def done(result: str) -> None:
        delivered.append((threading.get_ident(), result))
        finished.set()

    def job() -> str:
        jobs.append(threading.get_ident())
        return "result"

    work(job, done)
    assert finished.wait(5)
    assert jobs[0] != caller
    assert delivered[0][1] == "result"


def test_a_check_that_breaks_is_reported_as_unreachable_not_lost(tmp_path: Path) -> None:
    path = tmp_path / "shell.json"
    failed: list[tuple[str, str]] = []

    def broken(address, app, *, trusted):  # noqa: ANN001, ANN202
        raise RuntimeError("boom")

    connector = Connector(
        "computes",
        book=ServerBook("computes", local_origin=None, local_label="x", path=path),
        trust=TrustStore(path),
        switch=lambda _: None,
        fail=lambda code, message: failed.append((code, message)),
        check=broken,
        work=lambda job, done: done(job()),
    )
    connector.connect(SERVER)
    assert [code for code, _ in failed] == ["unreachable"]
