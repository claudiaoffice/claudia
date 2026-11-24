"""The interactive API description is off unless the administrator asks for it (SEC-14).

FastAPI's page loads its script and style from a CDN, so opening it tells a third party about the server and runs a
script from there: against the privacy promise. It is served only with ``--api-docs``.
"""

from starlette.testclient import TestClient

from claudia_core.testing import ListModel
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.cli import build_parser
from claudia_server.hub import Hub, MemoryProvider


def _app(**options):
    return create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(cost=2**4), **options)


def test_a_server_does_not_serve_the_api_description_by_default():
    with TestClient(_app()) as client:
        assert client.get("/api/swagger").status_code == 404


def test_the_landing_page_names_no_page_that_is_not_served():
    with TestClient(_app()) as client:
        assert "/api/swagger" not in client.get("/").text


def test_the_administrator_can_ask_for_the_api_description():
    with TestClient(_app(api_docs=True)) as client:
        assert client.get("/api/swagger").status_code == 200
        assert "/api/swagger" in client.get("/").text


def test_the_command_line_has_a_switch_for_it_that_is_off():
    assert build_parser().parse_args([]).api_docs is False
    assert build_parser().parse_args(["--api-docs"]).api_docs is True
