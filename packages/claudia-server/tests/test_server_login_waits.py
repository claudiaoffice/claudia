"""The waits after failed logins, at the doors of the server: a document's ``hello`` (password and recovery key) and the
administrator's sign-in (D1266, SEC-11). The counting itself is ``test_server_login_throttle.py``.
"""

import json

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from claudia_container import KdfParams
from claudia_core.testing import FakeClock, ListModel
from claudia_server import Hub, MemoryProvider, ScryptDirectory, create_app
from claudia_server.admin import AdminDirectory
from claudia_server.admin_api import AdminContext, AiRuntime
from claudia_server.admin_sessions import AdminSessions
from claudia_server.login_throttle import LoginThrottle
from claudia_server.sealed import SealedDocuments
from claudia_server.server_settings import ServerSettings

PASSWORD = "correct horse battery"
TOO_MANY = (4429, "too_many_tries")


class CountingDirectory(ScryptDirectory):
    """Counts the checks of a password: a refused wait must not cost one."""

    def __init__(self):
        super().__init__(cost=2**4)
        self.verified = 0

    def verify(self, doc_id, credentials):
        self.verified += 1
        return super().verify(doc_id, credentials)


@pytest.fixture
def clock():
    return FakeClock()


def serve(clock, *, directory=None, throttle=None, **options):
    hub = Hub(MemoryProvider(ListModel))
    throttle = throttle or LoginThrottle(clock=clock.lock_time)
    return create_app(hub, directory or CountingDirectory(), login_throttle=throttle, **options)


def hello(user="ann", password=PASSWORD, create=False, **extra):
    return json.dumps(
        {"id": 1, "method": "hello", "params": {"user": user, "password": password, "create": create, **extra}}
    )


def answer(client, doc="plan", headers=None, **params):
    """``"ok"``, or ``(close code, error code)``; with the error frame as the third item for a wait."""
    with client.websocket_connect(f"/api/docs/{doc}/ws", headers=headers or {}) as ws:
        ws.send_text(hello(**params))
        frame = ws.receive_json()
        if frame["ok"]:
            return "ok"
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        return closed.value.code, frame["error"]["code"], frame["error"]


def codes(result):
    return result if result == "ok" else result[:2]


@pytest.fixture
def made(clock):
    """A server with the document ``plan`` that ann made."""
    directory = CountingDirectory()
    with TestClient(serve(clock, directory=directory)) as client:
        assert answer(client, create=True) == "ok"
        yield client, directory


# ------------------------------------------------------------------------------------------ the document's hello
def test_three_wrong_passwords_are_free_and_the_next_login_has_to_wait(made, clock):
    client, _ = made
    for _ in range(3):
        assert codes(answer(client, password="not the password")) == (4401, "unauthorized")
    assert codes(answer(client, password="not the password")) == (4401, "unauthorized"), "the fourth is still looked at"
    refused = answer(client)  # the right password, inside the wait
    assert codes(refused) == TOO_MANY
    assert refused[2]["retry_after"] == 1


def test_a_login_inside_the_wait_costs_no_hashing(made):
    client, directory = made
    for _ in range(4):
        answer(client, password="wrong")
    before = directory.verified
    for _ in range(3):
        assert codes(answer(client)) == TOO_MANY
    assert directory.verified == before, "a guesser who waits for nothing costs the server nothing"


def test_the_right_password_is_let_in_when_the_wait_is_over_and_the_address_starts_again(made, clock):
    client, _ = made
    for _ in range(5):
        answer(client, password="wrong")
    assert codes(answer(client)) == TOO_MANY
    clock.advance(2.5)
    assert answer(client) == "ok"
    for n in range(3):  # a success cleared what the address had failed: three free tries again (at other names)
        assert codes(answer(client, user=f"zed{n}", password="wrong")) == (4401, "unauthorized")


def test_the_wait_is_said_in_the_language_of_the_window(made):
    client, _ = made
    for _ in range(4):
        answer(client, password="wrong")
    english = answer(client)[2]["message"]
    german = answer(client, locale="de")[2]["message"]
    assert "Try again in 1 second" in english
    assert german != english and "1" in german


def test_a_document_that_does_not_exist_counts_like_one_that_does(clock):
    with TestClient(serve(clock)) as client:
        for _ in range(4):
            assert codes(answer(client, "no-such-document", user="x", password="y")) == (4401, "unauthorized")
        assert codes(answer(client, "no-such-document", user="x", password="y")) == TOO_MANY
        assert codes(answer(client, "another-one", user="x", password="y")) == TOO_MANY, "the address waits"


def test_a_stranger_guessing_a_name_from_many_addresses_delays_her_by_ten_seconds_at_most(clock):
    directory = CountingDirectory()
    with TestClient(serve(clock, directory=directory, proxy_hops=1)) as client:
        assert answer(client, create=True) == "ok"
        for n in range(9):
            answer(client, password="guess", headers={"x-forwarded-for": f"198.51.100.{n}"})
        owner = answer(client, headers={"x-forwarded-for": "192.0.2.99"})
        assert codes(owner) == TOO_MANY and owner[2]["retry_after"] <= 10
        clock.advance(10.1)
        assert answer(client, headers={"x-forwarded-for": "192.0.2.99"}) == "ok", "nothing is locked for good"


def test_other_names_in_the_same_document_are_not_slowed_by_a_guess_at_one(clock):
    with TestClient(serve(clock, proxy_hops=1)) as client:
        assert answer(client, create=True) == "ok"
        for n in range(9):
            answer(client, user="ann", password="guess", headers={"x-forwarded-for": f"198.51.100.{n}"})
        assert answer(client, user="ann", headers={"x-forwarded-for": "192.0.2.1"})[0] == 4429
        directory_free = answer(client, user="ben", password="whatever", headers={"x-forwarded-for": "192.0.2.2"})
        assert codes(directory_free) == (4401, "unauthorized"), "ben is looked at, not made to wait"


def test_a_recovery_key_is_guessed_at_no_faster_than_a_password(clock, tmp_path):
    store = SealedDocuments(tmp_path, ListModel, kdf=KdfParams(iterations=1, memory_kib=64, lanes=1))
    app = create_app(Hub(store), store, login_throttle=LoginThrottle(clock=clock.lock_time))
    with TestClient(app) as client:
        assert answer(client, create=True, password="Correct-Horse-9") == "ok"
        for _ in range(4):
            answer(client, recovery_key="-".join(["AAAA"] * 13), password="A-new-Password-1")
        assert codes(answer(client, recovery_key="-".join(["AAAA"] * 13), password="A-new-Password-1")) == TOO_MANY


def test_the_waits_are_on_by_default(made):
    """A server made without a throttle of its own has one (the tests above inject theirs for the clock)."""
    hub = Hub(MemoryProvider(ListModel))
    with TestClient(create_app(hub, ScryptDirectory(cost=2**4))) as client:
        assert answer(client, create=True) == "ok"
        for _ in range(4):
            answer(client, password="wrong")
        assert codes(answer(client)) == TOO_MANY


def test_garbage_in_the_credentials_is_refused_and_does_not_break_the_counting(made):
    client, _ = made
    for _ in range(5):
        with client.websocket_connect("/api/docs/plan/ws") as ws:
            ws.send_text(json.dumps({"id": 1, "method": "hello", "params": {"user": 7, "password": None}}))
            assert ws.receive_json()["ok"] is False


# ------------------------------------------------------------------------------------------ the administrator's sign-in
class CountingAdmins(AdminDirectory):
    def __init__(self):
        super().__init__(cost=2**4)
        self.verified = 0

    def verify(self, name, password):
        self.verified += 1
        return super().verify(name, password)


@pytest.fixture
def admin_server(clock, tmp_path):
    admins = CountingAdmins()
    context = AdminContext(
        admins=admins,
        sessions=AdminSessions(),
        settings=ServerSettings(max_documents=100),
        state_dir=tmp_path,
        ai=AiRuntime(models=(ListModel,), enabled=False),
        exposed=True,
    )
    app = create_app(
        Hub(MemoryProvider(ListModel)),
        ScryptDirectory(),
        admin=context,
        login_throttle=LoginThrottle(clock=clock.lock_time),
    )
    with TestClient(app) as client:
        assert client.post("/api/admin/setup", json={"name": "tobi", "password": PASSWORD}).status_code == 200
        yield client, admins


def login(client, password=PASSWORD, name="tobi"):
    return client.post("/api/admin/login", json={"name": name, "password": password})


def test_the_administrators_sign_in_waits_after_three_free_failures(admin_server, clock):
    client, _ = admin_server
    for _ in range(4):
        assert login(client, "wrong").status_code == 401
    refused = login(client)
    assert refused.status_code == 429
    assert refused.headers["retry-after"] == "1" and refused.json()["retry_after"] == 1
    clock.advance(1.1)
    assert login(client).status_code == 200


def test_the_administrators_sign_in_inside_a_wait_costs_no_hashing(admin_server):
    client, admins = admin_server
    for _ in range(4):
        login(client, "wrong")
    before = admins.verified
    assert login(client).status_code == 429 and login(client).status_code == 429
    assert admins.verified == before


def test_an_address_that_failed_at_the_administrators_door_waits_at_the_documents_too(admin_server):
    client, _ = admin_server
    for _ in range(6):
        login(client, "wrong")
    assert codes(answer(client, create=True)) == TOO_MANY
