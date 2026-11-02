"""Plain HTTP on the redirect port only sends people to the secure address."""

import socket
import urllib.error
import urllib.request

import pytest

from claudia_server.redirect import location_for, start


def test_the_secure_address_is_built_from_what_was_asked_for():
    head = b"GET /api/health?x=1 HTTP/1.1\r\nHost: claudia.example.org:8080\r\nAccept: */*\r\n\r\n"
    assert location_for(head, 8765, "localhost") == "https://claudia.example.org:8765/api/health?x=1"
    assert location_for(head, 443, "localhost") == "https://claudia.example.org/api/health?x=1"
    assert location_for(b"GET / HTTP/1.1\r\nHost: [::1]:80\r\n\r\n", 8765, "x") == "https://[::1]:8765/"


@pytest.mark.parametrize(
    "head",
    [
        b"GET /a\r\nb HTTP/1.1\r\n\r\n",
        b"GET /ok HTTP/1.1\r\nHost: evil.example/\r\nX: y\r\n\r\n",
        b"GET /ok HTTP/1.1\r\nHost: a.example\r\nbad\r\n\r\n",
    ],
)
def test_nothing_from_the_request_can_split_the_answer(head):
    where = location_for(head, 8765, "localhost")
    assert "\r" not in where and "\n" not in where and " " not in where
    assert "evil.example/" not in where


def test_a_real_request_is_redirected():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    start("127.0.0.1", port, 8765)

    class NoFollow(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kw):
            return None

    opener = urllib.request.build_opener(NoFollow)
    with pytest.raises(urllib.error.HTTPError) as moved:
        opener.open(f"http://127.0.0.1:{port}/docs/plan", timeout=5)
    assert moved.value.code == 301
    assert moved.value.headers["Location"] == "https://127.0.0.1:8765/docs/plan"


def test_a_taken_port_is_reported():
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        with pytest.raises(OSError):
            start("127.0.0.1", taken.getsockname()[1], 8765)
