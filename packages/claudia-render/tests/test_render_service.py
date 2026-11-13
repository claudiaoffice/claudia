"""The registry of container types and the service that renders them: one place where the rules are kept (D341-D343).

A plugin only runs; the service finds its tools, caps its limits, refuses what it forbids, caches and reports."""

import json

import pytest
from conftest import BOXER, fake_tool, posix_only, runs_in_a_loop

from claudia_render import (
    CliPlugin,
    ManifestError,
    PluginRegistry,
    RenderFailed,
    RenderPolicy,
    RenderService,
    ToolRegistry,
    ToolUnavailable,
    UnknownType,
    parse_manifest,
)

pytestmark = posix_only


def boxer_manifest(**changes) -> dict:
    base = {
        "api": 1,
        "type": "boxer",
        "version": "1.0",
        "title": "Boxer",
        "requires": [{"tool": "boxer", "version_at_least": "2.0"}],
        "params": [{"name": "theme", "type": "string", "default": "plain", "choices": ["plain", "dark"]}],
        "cli": {"argv": ["${tool.boxer}", "${input}", "${output}"], "output": "out.svg", "diagnostics": "typst-short"},
        "editor": {"syntax": "boxer", "example": "hello", "ai_hint": "One line of text per box."},
        "max_source_chars": 50,
    }
    return {**base, **changes}


def make(tmp_path, *, tool=True, policy=None, **changes):
    plugins = PluginRegistry()
    plugins.register(CliPlugin(parse_manifest(boxer_manifest(**changes)), tmp_path / "work"))
    if tool:
        program = fake_tool(tmp_path / "bin", "boxer", BOXER)
        tools = ToolRegistry({"boxer": str(program)})
    else:
        tools = ToolRegistry({"boxer": str(tmp_path / "nowhere" / "boxer")})
    return RenderService(plugins, tools, tmp_path / "service", policy or RenderPolicy()), plugins


# -- the registry ----------------------------------------------------------------------------------------------------
def test_a_type_is_registered_once():
    plugins = PluginRegistry()
    plugin = CliPlugin(parse_manifest(boxer_manifest()), "/tmp/w")  # noqa: S108
    plugins.register(plugin)
    with pytest.raises(ValueError, match="already"):
        plugins.register(CliPlugin(parse_manifest(boxer_manifest(version="2.0")), "/tmp/w"))  # noqa: S108
    assert plugins.get("boxer") is plugin and [p.manifest.type for p in plugins.plugins()] == ["boxer"]


def test_an_unknown_type_is_named_with_the_ones_there_are():
    plugins = PluginRegistry()
    plugins.register(CliPlugin(parse_manifest(boxer_manifest()), "/tmp/w"))  # noqa: S108
    with pytest.raises(UnknownType, match="boxer"):
        plugins.get("graphviz")


def test_manifests_in_a_folder_are_loaded_and_a_bad_one_does_not_stop_the_rest(tmp_path):
    folder = tmp_path / "plugins"
    folder.mkdir()
    (folder / "good.json").write_text(json.dumps(boxer_manifest()))
    (folder / "broken.json").write_text("{not json")
    (folder / "wrong.json").write_text(json.dumps(boxer_manifest(type="other", colour="red")))
    (folder / "notes.txt").write_text("ignored")
    plugins = PluginRegistry()
    report = plugins.load_directory(folder, tmp_path / "work")
    assert [p.manifest.type for p in plugins.plugins()] == ["boxer"]
    assert {r.file: r.error is None for r in report} == {"good.json": True, "broken.json": False, "wrong.json": False}
    assert any("colour" in (r.error or "") for r in report)


def test_a_folder_can_bring_data_but_never_code(tmp_path):
    folder = tmp_path / "plugins"
    folder.mkdir()
    data = boxer_manifest(adapter="latex")
    del data["cli"]
    (folder / "adapter.json").write_text(json.dumps(data))
    plugins = PluginRegistry()
    (report,) = plugins.load_directory(folder, tmp_path / "work")
    assert report.error is not None and "adapter" in report.error and plugins.plugins() == ()


def test_a_folder_cannot_replace_a_type_that_is_already_there(tmp_path):
    folder = tmp_path / "plugins"
    folder.mkdir()
    (folder / "again.json").write_text(json.dumps(boxer_manifest(version="9.0")))
    plugins = PluginRegistry()
    plugins.register(CliPlugin(parse_manifest(boxer_manifest()), tmp_path / "work"))
    (report,) = plugins.load_directory(folder, tmp_path / "work")
    assert report.error is not None and "already" in report.error
    assert plugins.get("boxer").manifest.version == "1.0"


def test_a_folder_that_is_not_there_is_no_error(tmp_path):
    assert PluginRegistry().load_directory(tmp_path / "nope", tmp_path / "work") == ()


def test_manifest_errors_are_manifest_errors_for_whoever_catches_them():
    assert issubclass(ManifestError, ValueError)


# -- rendering ------------------------------------------------------------------------------------------------------
@runs_in_a_loop
async def test_a_text_is_rendered_to_a_picture_with_a_size_and_a_note_of_what_made_it(tmp_path):
    service, _ = make(tmp_path)
    done = await service.render("boxer", "hello", {})
    assert done.svg.startswith("<svg") and (done.width, done.height) == (50.0, 20.0) and not done.cached
    assert done.renderer.startswith("boxer 1.0 | boxer 2.5.1 ") and len(done.renderer) <= 200


@runs_in_a_loop
async def test_the_same_text_is_found_in_the_cache_the_second_time_and_a_changed_setting_is_not(tmp_path):
    service, _ = make(tmp_path)
    first = await service.render("boxer", "hello", {})
    again = await service.render("boxer", "hello", {"theme": "plain"})  # the default, said out loud: the same job
    other = await service.render("boxer", "hello", {"theme": "dark"})
    assert (first.cached, again.cached, other.cached) == (False, True, False)
    assert again.svg == first.svg and (again.width, again.height) == (first.width, first.height)


@runs_in_a_loop
async def test_a_new_version_of_the_plugin_does_not_find_the_old_pictures(tmp_path):
    service, _ = make(tmp_path)
    await service.render("boxer", "hello", {})
    newer, _ = make(tmp_path, version="1.1")
    assert (await newer.render("boxer", "hello", {})).cached is False


@runs_in_a_loop
async def test_a_failure_is_not_remembered(tmp_path):
    service, _ = make(tmp_path)
    with pytest.raises(RenderFailed) as failed:
        await service.render("boxer", "fine\nFAIL", {})
    assert failed.value.diagnostics[0].line == 2
    with pytest.raises(RenderFailed):
        await service.render("boxer", "fine\nFAIL", {})


@runs_in_a_loop
async def test_an_unknown_type_and_a_wrong_setting_are_refused_before_anything_runs(tmp_path):
    service, _ = make(tmp_path)
    with pytest.raises(UnknownType):
        await service.render("graphviz", "x", {})
    with pytest.raises(ValueError, match="theme"):
        await service.render("boxer", "x", {"theme": "neon"})
    with pytest.raises(ValueError, match="no such setting"):
        await service.render("boxer", "x", {"colour": "red"})


@runs_in_a_loop
async def test_a_text_that_is_too_long_or_empty_is_refused_with_a_sentence(tmp_path):
    service, _ = make(tmp_path)
    with pytest.raises(RenderFailed, match="at most 50"):
        await service.render("boxer", "x" * 51, {})
    with pytest.raises(RenderFailed, match="nothing to render"):
        await service.render("boxer", "  \n", {})


@runs_in_a_loop
async def test_a_text_the_plugin_forbids_is_refused_with_its_own_words_and_the_line(tmp_path):
    forbid = [{"pattern": "@evil", "message": "evil is not available"}]
    service, _ = make(tmp_path, forbid=forbid)
    with pytest.raises(RenderFailed, match="evil is not available") as failed:
        await service.render("boxer", "fine\nuse @evil here", {})
    assert failed.value.diagnostics[0].line == 2


@runs_in_a_loop
async def test_a_missing_tool_is_said_so_and_installing_it_needs_no_restart(tmp_path):
    service, _ = make(tmp_path, tool=False)
    with pytest.raises(ToolUnavailable, match="boxer"):
        await service.render("boxer", "x", {})
    fake_tool(tmp_path / "nowhere", "boxer", BOXER)
    assert (await service.render("boxer", "x", {})).svg.startswith("<svg")


@runs_in_a_loop
async def test_a_tool_that_is_too_old_is_refused_with_the_versions(tmp_path):
    service, _ = make(tmp_path, requires=[{"tool": "boxer", "version_at_least": "3.0"}])
    with pytest.raises(ToolUnavailable, match=r"2\.5\.1 is too old.*3\.0"):
        await service.render("boxer", "x", {})


@runs_in_a_loop
async def test_the_servers_policy_caps_what_a_plugin_asks_for(tmp_path):
    slow_tool = """
        import sys, time
        if "--version" in sys.argv:
            print("boxer 2.5.1"); raise SystemExit(0)
        time.sleep(30)
    """
    plugins = PluginRegistry()
    plugins.register(CliPlugin(parse_manifest(boxer_manifest(limits={"seconds": 300})), tmp_path / "work"))
    program = fake_tool(tmp_path / "bin", "boxer", slow_tool)
    service = RenderService(plugins, ToolRegistry({"boxer": str(program)}), tmp_path / "s", RenderPolicy(max_seconds=1))
    with pytest.raises(RenderFailed, match="took longer than 1 s"):
        await service.render("boxer", "x", {})


@runs_in_a_loop
async def test_only_so_many_renders_run_at_once(tmp_path):
    gate = """
        import os, sys, time
        if "--version" in sys.argv:
            print("boxer 2.5.1"); raise SystemExit(0)
        marker = os.environ["TMPDIR"] + "/../running"
        open(marker + str(os.getpid()), "w").close()
        time.sleep(0.5)
        open(sys.argv[2], "w").write('<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>')
    """
    import asyncio

    plugins = PluginRegistry()
    plugins.register(CliPlugin(parse_manifest(boxer_manifest()), tmp_path / "work"))
    program = fake_tool(tmp_path / "bin", "boxer", gate)
    service = RenderService(plugins, ToolRegistry({"boxer": str(program)}), tmp_path / "s", RenderPolicy(concurrency=1))
    started = asyncio.get_running_loop().time()
    await asyncio.gather(*(service.render("boxer", f"t{n}", {}) for n in range(3)))
    assert asyncio.get_running_loop().time() - started >= 1.4, "three half-second jobs, one at a time"


# -- what clients and the AI are told ----------------------------------------------------------------------------------
@runs_in_a_loop
async def test_the_types_are_described_with_whether_their_tools_work(tmp_path):
    service, _ = make(tmp_path)
    (one,) = await service.describe_types()
    assert one["type"] == "boxer" and one["available"] is True and one["problem"] == ""
    assert one["editor"]["ai_hint"] == "One line of text per box."
    assert "argv" not in json.dumps(one), "how a tool is run is nobody's business but the server's"
    broken, _ = make(tmp_path / "other", tool=False)
    (two,) = await broken.describe_types()
    assert two["available"] is False and "boxer" in two["problem"]
