"""The tools a server has registered: which program stands behind a logical name, and whether it works (D342).

The administrator owns this table (D38: whoever controls the server's folder controls what runs); a plugin only *names*
a tool. Resolution is lazy, so a server without a tool starts and the first request says what is missing."""

import pytest
from conftest import BOXER, fake_tool, posix_only, runs_in_a_loop

from claudia_render import ToolEntry, ToolRegistry, ToolRequirement, ToolUnavailable

pytestmark = posix_only


def registry(tmp_path, **settings) -> ToolRegistry:
    return ToolRegistry(settings)


@runs_in_a_loop
async def test_a_logical_name_resolves_to_the_program_the_administrator_gave(tmp_path):
    program = fake_tool(tmp_path / "bin", "boxer", BOXER)
    tool = await registry(tmp_path, boxer={"path": str(program)}).resolve(ToolRequirement("boxer"))
    assert (tool.name, tool.program, tool.version) == ("boxer", program, "2.5.1")


@runs_in_a_loop
async def test_a_plain_path_is_enough_as_a_setting(tmp_path):
    program = fake_tool(tmp_path / "bin", "boxer", BOXER)
    tool = await registry(tmp_path, boxer=str(program)).resolve(ToolRequirement("boxer"))
    assert tool.program == program


@runs_in_a_loop
async def test_a_tool_nobody_configured_is_looked_for_on_the_path(tmp_path, monkeypatch):
    fake_tool(tmp_path / "bin", "boxer", BOXER)
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    assert (await registry(tmp_path).resolve(ToolRequirement("boxer"))).version == "2.5.1"


@runs_in_a_loop
async def test_the_options_of_a_tool_travel_with_it_and_change_its_identity(tmp_path):
    program = fake_tool(tmp_path / "bin", "boxer", BOXER)
    plain = await registry(tmp_path, boxer={"path": str(program)}).resolve(ToolRequirement("boxer"))
    with_option = await registry(tmp_path, boxer={"path": str(program), "browser": "/usr/bin/x"}).resolve(
        ToolRequirement("boxer")
    )
    assert with_option.options == {"browser": "/usr/bin/x"} and plain.options == {}
    assert plain.identity != with_option.identity, "a renderer made with other options may draw something else"
    assert plain.identity.startswith("boxer 2.5.1")


@runs_in_a_loop
async def test_a_missing_tool_says_which_setting_to_change_and_does_not_poison_later_tries(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    tools = registry(tmp_path)
    with pytest.raises(ToolUnavailable, match=r"boxer.*tools\.boxer\.path") as error:
        await tools.resolve(ToolRequirement("boxer"))
    assert error.value.tool == "boxer"
    fake_tool(tmp_path / "empty", "boxer", BOXER)  # the administrator installs it meanwhile
    assert (await tools.resolve(ToolRequirement("boxer"))).version == "2.5.1"


@runs_in_a_loop
async def test_a_tool_that_does_not_run_is_unavailable_with_what_it_said(tmp_path):
    broken = fake_tool(tmp_path / "bin", "boxer", "import sys\nprint('cannot start: no display')\nsys.exit(3)\n")
    with pytest.raises(ToolUnavailable, match="no display"):
        await registry(tmp_path, boxer=str(broken)).resolve(ToolRequirement("boxer"))


@runs_in_a_loop
async def test_the_version_a_plugin_needs_is_compared_as_numbers_not_as_text(tmp_path):
    program = fake_tool(tmp_path / "bin", "boxer", BOXER)  # 2.5.1
    tools = registry(tmp_path, boxer=str(program))
    await tools.resolve(ToolRequirement("boxer", "2.5"))
    await tools.resolve(ToolRequirement("boxer", "2.5.1"))
    with pytest.raises(ToolUnavailable, match=r"2\.10"):
        await tools.resolve(ToolRequirement("boxer", "2.10"))  # 2.5.1 is older than 2.10, though "2.5" > "2.1" as text


@runs_in_a_loop
async def test_a_tool_whose_version_cannot_be_read_does_not_pass_a_version_requirement(tmp_path):
    odd = fake_tool(tmp_path / "bin", "boxer", "print('boxer, the best one')\n")
    with pytest.raises(ToolUnavailable, match="version"):
        await registry(tmp_path, boxer=str(odd)).resolve(ToolRequirement("boxer", "1.0"))
    assert (await registry(tmp_path, boxer=str(odd)).resolve(ToolRequirement("boxer"))).version == "unknown"


@runs_in_a_loop
async def test_a_tool_that_reports_its_version_another_way_is_asked_that_way(tmp_path):
    program = fake_tool(tmp_path / "bin", "boxer", "import sys\nprint('boxer 7.1' if '-v' in sys.argv else 'huh')\n")
    tools = ToolRegistry({"boxer": str(program)}, version_args={"boxer": ("-v",)})
    assert (await tools.resolve(ToolRequirement("boxer"))).version == "7.1"


@runs_in_a_loop
async def test_a_resolved_tool_is_remembered_until_somebody_asks_to_look_again(tmp_path):
    program = fake_tool(tmp_path / "bin", "boxer", BOXER)
    tools = registry(tmp_path, boxer=str(program))
    first = await tools.resolve(ToolRequirement("boxer"))
    program.unlink()
    assert await tools.resolve(ToolRequirement("boxer")) is first
    tools.forget()
    with pytest.raises(ToolUnavailable):
        await tools.resolve(ToolRequirement("boxer"))


@runs_in_a_loop
async def test_the_status_of_a_tool_is_a_sentence_for_the_administrator_never_an_exception(tmp_path, monkeypatch):
    program = fake_tool(tmp_path / "bin", "boxer", BOXER)
    ok = await registry(tmp_path, boxer=str(program)).status("boxer")
    assert (ok.ok, ok.version) == (True, "2.5.1") and str(program) in ok.detail
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    missing = await registry(tmp_path).status("boxer")
    assert missing.ok is False and "tools.boxer.path" in missing.hint


def test_a_setting_that_is_not_a_tool_entry_is_refused_at_once(tmp_path):
    with pytest.raises(ValueError, match="tool"):
        ToolRegistry({"Boxer": "x"})
    with pytest.raises(ValueError, match="path"):
        ToolRegistry({"boxer": {"path": 3}})
    with pytest.raises(ValueError, match="option"):
        ToolRegistry({"boxer": {"Bad-Name": "x"}})


def test_the_registry_lists_what_the_administrator_configured(tmp_path):
    tools = ToolRegistry({"b": "/x/b", "a": {"path": "/x/a", "mode": "fast"}})
    assert tools.configured() == (ToolEntry("a", "/x/a", {"mode": "fast"}), ToolEntry("b", "/x/b", {}))
