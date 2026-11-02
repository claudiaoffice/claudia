"""The command line: what it refuses, and what it prepares."""

import pytest

from claudia_server.cli import UsageError, load_model, make_plan


def plan(*args, tmp_path):
    return make_plan([*args, "--state-dir", str(tmp_path)])


def test_the_default_plan_is_encrypted_and_local(tmp_path):
    result = plan(tmp_path=tmp_path)
    options = result.uvicorn_options
    assert options["host"] == "127.0.0.1" and options["ssl_certfile"].endswith("cert.pem")
    assert any("fingerprint SHA256:" in line for line in result.banner)
    assert any("no web app" in line for line in result.banner)


def test_no_tls_says_so_loudly(tmp_path):
    result = plan("--no-tls", tmp_path=tmp_path)
    assert "ssl_certfile" not in result.uvicorn_options
    assert any(line.startswith("WARNING: no TLS") for line in result.banner)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--no-tls", "--tls-cert", "a.pem"], "contradict"),
        (["--no-tls", "--redirect-port", "8080"], "needs TLS"),
        (["--tls-cert", "a.pem"], "go together"),
        (["--port", "0"], "--port"),
        (["--model", "nonsense"], "module:Class"),
        (["--model", "no_such_module:Thing"], "cannot load the model"),
        (["--web", "/nonexistent"], "built web app"),
    ],
)
def test_impossible_options_are_refused_with_a_reason(tmp_path, args, message):
    with pytest.raises(UsageError, match=message):
        plan(*args, tmp_path=tmp_path)


def test_the_model_is_loaded_by_name():
    from claudia_core.testing import ListModel

    assert load_model("claudia_core.testing:ListModel") is ListModel


def test_a_folder_makes_the_store_persistent(tmp_path):
    result = plan("--no-tls", "--dir", str(tmp_path / "data"), tmp_path=tmp_path)
    assert any("not encrypted" in line for line in result.banner)
    assert (tmp_path / "data" / "docs").is_dir()


def test_listing_can_be_switched_off_from_the_command_line(tmp_path):
    from starlette.testclient import TestClient

    on = TestClient(plan("--no-tls", tmp_path=tmp_path).app)
    off = TestClient(plan("--no-tls", "--no-list", tmp_path=tmp_path).app)
    assert on.get("/api/docs").status_code == 200 and off.get("/api/docs").status_code == 404


def test_a_workbook_server_offers_the_spreadsheet_methods_and_others_do_not(tmp_path):
    from starlette.testclient import TestClient

    def methods(*extra):
        client = TestClient(plan("--no-tls", *extra, tmp_path=tmp_path).app)
        return set(client.get("/api/protocol").json()["methods"])

    assert {"cells", "set_cells", "sheets"} <= methods()
    assert "cells" not in methods("--model", "claudia_core.testing:ListModel")


def test_workbooks_get_the_stand_in_assistant_unless_switched_off(tmp_path):
    import asyncio

    async def users(*extra):
        hosted = await plan("--no-tls", *extra, tmp_path=tmp_path).app.state.hub.open("x", create=True)
        return hosted.users()

    assert asyncio.run(users()) == ["ai"]
    assert asyncio.run(users("--no-assistant")) == []
