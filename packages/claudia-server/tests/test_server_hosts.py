"""A server answers only to its own names, so a web page cannot reach it by rebinding its DNS name (SEC-01).

Before this, the Origin check trusted the ``Host`` header the page itself sent: a page at ``evil.example`` whose name
was pointed at 127.0.0.1 sent ``Host: evil.example`` and ``Origin: http://evil.example``, the two matched, and the page
could list, create and try passwords on the documents of a server on its visitor's computer.
"""

import asyncio
import json

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from claudia_core.testing import ListModel
from claudia_server import Hub, MemoryProvider, ScryptDirectory, create_app
from claudia_server.hosts import AllowedHosts, HostGuard

PASSWORD = "correct horse battery"
REBOUND = "http://evil.example:8765"


def served(provider=None, **options):
    provider = provider or MemoryProvider(ListModel)
    return create_app(Hub(provider), ScryptDirectory(cost=2**4), **options)


def hello(create=True):
    return {"id": 1, "method": "hello", "params": {"user": "ann", "password": PASSWORD, "create": create}}


# ------------------------------------------------------------------------------------ the rule itself
@pytest.mark.parametrize(
    "header",
    [
        "localhost",
        "localhost:8765",
        "LocalHost:8765",
        "localhost.:8765",
        "127.0.0.1",
        "127.0.0.1:8765",
        "[::1]",
        "[::1]:8765",
        "192.168.1.20:8765",
        "[2001:db8::1]:8765",
    ],
)
def test_this_computer_and_ip_addresses_are_allowed(header):
    """An IP address cannot be rebound: a page needs a *name* whose answer it can change."""
    assert AllowedHosts().allows(header)


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "evil.example",
        "evil.example:8765",
        "localhost.evil.example",
        "evil.localhost",
        "0.0.0.0:8765",  # some browsers send requests to it as if it were this computer
        "[::]:8765",
        "evil.example@127.0.0.1",
        "127.0.0.1@evil.example",
        "evil.example/127.0.0.1",
        "127.0.0.1 evil.example",
        "evil.example:80:80",
        "evil.example:",
        "127.0.0.1:port",
    ],
)
def test_other_names_and_anything_that_is_not_a_plain_host_are_refused(header):
    assert not AllowedHosts().allows(header)


def test_configured_names_are_allowed_whatever_their_case_and_port():
    hosts = AllowedHosts(["Claudia.Example.org", "nas"])
    assert hosts.allows("claudia.example.org:8443")
    assert hosts.allows("NAS")
    assert not hosts.allows("example.org")
    assert not hosts.allows("evil.claudia.example.org")


def test_only_ascii_letters_count_as_letters():
    """Unicode case folding must not let a look-alike (the Kelvin sign) turn into a configured name."""
    assert not AllowedHosts(["kasse"]).allows("\u212aasse")
    assert not AllowedHosts(["kasse"]).allows("\u017fasse")
    with pytest.raises(ValueError, match="host name"):
        AllowedHosts(["\u212aasse"])


def test_a_name_with_a_port_in_the_configuration_means_the_name():
    assert AllowedHosts(["claudia.example.org:8443"]).allows("claudia.example.org")


@pytest.mark.parametrize("name", ["", "has space", "evil.example/path", "a@b", "[nonsense"])
def test_a_configured_name_that_is_not_a_host_name_is_refused_early(name):
    with pytest.raises(ValueError, match="host name"):
        AllowedHosts([name])


# ------------------------------------------------------------------- the attack, over the real app
def test_a_rebound_name_cannot_use_the_http_api():
    with TestClient(served(), base_url=REBOUND) as client:
        for path in ("/api/docs", "/api/health", "/api/protocol", "/api/swagger", "/"):
            assert client.get(path).status_code == 403, path


def test_a_rebound_name_cannot_create_a_document_even_when_origin_and_host_match():
    """The measured attack of SEC-01: both headers name the page itself, so the Origin check alone said yes."""
    provider = MemoryProvider(ListModel)
    with TestClient(served(provider), base_url=REBOUND) as client:
        with (
            pytest.raises(WebSocketDisconnect) as closed,
            client.websocket_connect("/api/docs/plan/ws", headers={"origin": REBOUND}) as ws,
        ):
            ws.send_text(json.dumps(hello()))
            ws.receive_json()
        assert closed.value.code == 4403
    assert not provider.exists("plan")


def test_a_client_that_sends_no_origin_is_refused_too_when_the_name_is_not_ours():
    with (
        TestClient(served(), base_url=REBOUND) as client,
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect("/api/docs/plan/ws"),
    ):
        pass
    assert closed.value.code == 4403


def test_the_refusal_says_how_to_add_a_name():
    with TestClient(served(), base_url=REBOUND) as client:
        reply = client.get("/api/health")
    assert "--allow-host" in reply.text


def test_a_preflight_from_a_rebound_name_gets_no_cors_headers():
    """The host check is the outermost layer, so even the CORS middleware never answers for a name that is not ours."""
    app = served(allowed_origins=["https://app.example"])
    with TestClient(app, base_url=REBOUND) as client:
        reply = client.options(
            "/api/docs", headers={"Origin": "https://app.example", "Access-Control-Request-Method": "GET"}
        )
    assert reply.status_code == 403
    assert "access-control-allow-origin" not in reply.headers


# ------------------------------------------------------------------ what must keep working
@pytest.mark.parametrize(
    "base",
    [
        "http://localhost",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
        "http://[::1]:8765",
        "http://192.168.1.20:8765",
    ],
)
def test_the_servers_own_addresses_work_for_http_and_websockets(base):
    provider = MemoryProvider(ListModel)
    with TestClient(served(provider), base_url=base) as client:
        assert client.get("/api/docs").status_code == 200
        with client.websocket_connect("/api/docs/plan/ws", headers={"origin": base}) as ws:
            ws.send_text(json.dumps(hello()))
            assert ws.receive_json()["ok"]
    assert provider.exists("plan")


def test_a_configured_name_works_and_its_neighbours_do_not():
    app = served(allowed_hosts=["claudia.example.org"])
    with TestClient(app, base_url="http://claudia.example.org") as ours:
        assert ours.get("/api/health").status_code == 200
        with ours.websocket_connect("/api/docs/plan/ws", headers={"origin": "http://claudia.example.org"}) as ws:
            ws.send_text(json.dumps(hello()))
            assert ws.receive_json()["ok"]
    with TestClient(app, base_url="http://other.example.org") as other:
        assert other.get("/api/health").status_code == 403


# ------------------------------------------------------------------------- the middleware, called directly
def call(guard, scope):
    """What the guard sent for ``scope`` (the messages), and the scopes it let through to the application."""
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        sent.append(message)

    asyncio.run(guard(scope, receive, send))
    return sent


def test_two_host_headers_are_one_too_many():
    """Nobody can say which of two Host headers the application, or a proxy before it, would take."""
    reached = []

    async def application(scope, receive, send):
        reached.append(scope["type"])

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"host", b"localhost"), (b"host", b"evil.example")],
    }
    sent = call(HostGuard(application, AllowedHosts()), scope)
    assert reached == [] and sent[0]["status"] == 403


def test_the_lifespan_has_no_host_and_passes_through():
    reached = []

    async def application(scope, receive, send):
        reached.append(scope["type"])

    call(HostGuard(application, AllowedHosts()), {"type": "lifespan", "headers": []})
    assert reached == ["lifespan"]
