"""A plugin that is only data: how a registered tool is asked for a picture, run in the sandbox (D343).

The fake tool stands in for any renderer: it answers ``--version``, reads the file it is given and writes an SVG."""

import json

import pytest
from conftest import BOXER, fake_tool, posix_only, runs_in_a_loop

from claudia_render import (
    CliPlugin,
    Diagnostic,
    RenderFailed,
    RenderRequest,
    ToolRegistry,
    ToolRequirement,
    parse_manifest,
)
from claudia_typeset import Limits

pytestmark = posix_only


def manifest_data(**cli):
    return {
        "api": 1,
        "type": "boxer",
        "version": "1.0",
        "title": "Boxer",
        "requires": [{"tool": "boxer"}],
        "params": [{"name": "theme", "type": "string", "default": "plain", "choices": ["plain", "dark"]}],
        "cli": {"argv": ["${tool.boxer}", "${input}", "${output}"], "output": "out.svg", **cli},
        "svg_elements": [],
    }


async def tools_for(tmp_path, body=BOXER, **options):
    program = fake_tool(tmp_path / "bin", "boxer", body)
    registry = ToolRegistry({"boxer": {"path": str(program), **options}})
    return {"boxer": await registry.resolve(ToolRequirement("boxer"))}


def plugin(tmp_path, **cli) -> CliPlugin:
    return CliPlugin(parse_manifest(manifest_data(**cli)), tmp_path / "work")


LIMITS = Limits(seconds=10, memory_mb=512, output_mb=2)


@runs_in_a_loop
async def test_the_tool_is_run_on_the_text_and_its_picture_comes_back_with_a_size(tmp_path):
    result = await plugin(tmp_path).render(
        RenderRequest("12345", {"theme": "plain"}), await tools_for(tmp_path), LIMITS
    )
    assert result.svg.startswith("<svg") and (result.width, result.height) == (50.0, 20.0)


@runs_in_a_loop
async def test_a_tool_that_writes_to_standard_output_is_read_from_there(tmp_path):
    result = await plugin(tmp_path, argv=["${tool.boxer}", "${input}"], output="stdout").render(
        RenderRequest("1234567890", {}), await tools_for(tmp_path), LIMITS
    )
    assert result.width == 100.0


@runs_in_a_loop
async def test_what_the_tool_complains_about_is_read_with_the_line_of_the_persons_text(tmp_path):
    with pytest.raises(RenderFailed) as failed:
        await plugin(tmp_path, diagnostics="typst-short").render(
            RenderRequest("fine\nFAIL", {}), await tools_for(tmp_path), LIMITS
        )
    assert failed.value.diagnostics == (Diagnostic("error", "no such box", 2, 5),)


@runs_in_a_loop
async def test_what_was_put_in_front_of_the_text_is_not_counted_in_a_line(tmp_path):
    with pytest.raises(RenderFailed) as failed:
        await plugin(tmp_path, diagnostics="typst-short", prefix="one\ntwo\n").render(
            RenderRequest("FAIL", {}), await tools_for(tmp_path), LIMITS
        )
    assert failed.value.diagnostics[0].line is None, "a complaint about what the plugin added has no line of the text"


@runs_in_a_loop
async def test_the_input_is_the_prefix_the_text_and_the_suffix(tmp_path):
    echo = """
        import sys
        if "--version" in sys.argv:
            print("echo 1.0"); raise SystemExit(0)
        text = open(sys.argv[1], encoding="utf-8").read()
        open(sys.argv[2], "w").write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><title>{text!r}</title></svg>'
        )
    """
    tools = await tools_for(tmp_path, echo)
    result = await plugin(tmp_path, prefix="[", suffix="]").render(RenderRequest("x", {}), tools, LIMITS)
    assert "'[x]'" in result.svg


@runs_in_a_loop
async def test_a_setting_reaches_the_tool_as_an_argument_and_only_as_a_whole_argument(tmp_path):
    spy = """
        import sys
        if "--version" in sys.argv:
            print("spy 1.0"); raise SystemExit(0)
        open(sys.argv[-1], "w").write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><desc>{sys.argv[1:-1]}</desc></svg>'
        )
    """
    tools = await tools_for(tmp_path, spy)
    result = await plugin(tmp_path, argv=["${tool.boxer}", "--theme=${param.theme}", "${output}"]).render(
        RenderRequest("x", {"theme": "dark"}), tools, LIMITS
    )
    assert "--theme=dark" in result.svg


@runs_in_a_loop
async def test_an_optional_option_of_the_tool_that_is_not_set_leaves_its_argument_out(tmp_path):
    spy = """
        import sys
        if "--version" in sys.argv:
            print("spy 1.0"); raise SystemExit(0)
        open(sys.argv[-1], "w").write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><desc>{sys.argv[1:-1]}</desc></svg>'
        )
    """
    argv = ["${tool.boxer}", "--font-path=${tool.boxer.fonts?}", "${output}"]
    without = await plugin(tmp_path, argv=argv).render(RenderRequest("x", {}), await tools_for(tmp_path, spy), LIMITS)
    assert "--font-path" not in without.svg
    with_it = await plugin(tmp_path, argv=argv).render(
        RenderRequest("x", {}), await tools_for(tmp_path, spy, fonts="/fonts"), LIMITS
    )
    assert "--font-path=/fonts" in with_it.svg


@runs_in_a_loop
async def test_support_files_are_written_as_structured_data_so_a_setting_cannot_break_out_of_it(tmp_path):
    dump = """
        import sys
        if "--version" in sys.argv:
            print("dump 1.0"); raise SystemExit(0)
        text = open("config.json", encoding="utf-8").read()
        open(sys.argv[2], "w").write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><desc>{text}</desc></svg>'
        )
    """
    files = {
        "config.json": {
            "theme": "${param.theme}",
            "extra": {"path": "${tool.boxer.chrome?}", "args": "${tool.boxer.args?}"},
        }
    }
    tools = await tools_for(tmp_path, dump, chrome="/usr/bin/chrome", args=["--no-sandbox"])
    result = await plugin(tmp_path, files=files).render(RenderRequest("x", {"theme": "dark"}), tools, LIMITS)
    written = json.loads(result.svg.split("<desc>")[1].split("</desc>")[0].replace("&quot;", '"'))
    assert written == {"theme": "dark", "extra": {"path": "/usr/bin/chrome", "args": ["--no-sandbox"]}}


@runs_in_a_loop
async def test_a_key_whose_optional_option_is_not_set_is_left_out_of_the_support_file(tmp_path):
    dump = """
        import sys
        if "--version" in sys.argv:
            print("dump 1.0"); raise SystemExit(0)
        text = open("config.json", encoding="utf-8").read()
        open(sys.argv[2], "w").write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><desc>{text}</desc></svg>'
        )
    """
    files = {"config.json": {"theme": "${param.theme}", "path": "${tool.boxer.chrome?}"}}
    result = await plugin(tmp_path, files=files).render(
        RenderRequest("x", {"theme": "dark"}), await tools_for(tmp_path, dump), LIMITS
    )
    assert "path" not in result.svg


@runs_in_a_loop
async def test_the_tool_runs_with_the_job_folder_as_its_home_and_nothing_of_the_servers_environment(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SECRET_TOKEN", "hunter2")
    probe = """
        import os, sys
        if "--version" in sys.argv:
            print("probe 1.0"); raise SystemExit(0)
        shown = {k: v for k, v in os.environ.items() if k in ("SECRET_TOKEN", "HOME", "PROXY_X")}
        open(sys.argv[2], "w").write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><desc>{shown}</desc></svg>'
        )
    """
    result = await plugin(tmp_path, env={"PROXY_X": "http://127.0.0.1:9"}).render(
        RenderRequest("x", {}), await tools_for(tmp_path, probe), LIMITS
    )
    assert "hunter2" not in result.svg and "127.0.0.1:9" in result.svg and "'HOME': '" in result.svg


@runs_in_a_loop
async def test_a_picture_that_is_not_only_drawing_is_refused(tmp_path):
    evil = """
        import sys
        if "--version" in sys.argv:
            print("evil 1.0"); raise SystemExit(0)
        open(sys.argv[2], "w").write(
            '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><script>alert(1)</script></svg>'
        )
    """
    with pytest.raises(RenderFailed, match="not allowed|never"):
        await plugin(tmp_path).render(RenderRequest("x", {}), await tools_for(tmp_path, evil), LIMITS)


@runs_in_a_loop
async def test_an_element_the_profile_allows_passes_and_one_that_is_never_allowed_does_not(tmp_path):
    texty = """
        import sys
        if "--version" in sys.argv:
            print("t 1.0"); raise SystemExit(0)
        open(sys.argv[2], "w").write(
            '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><text>hi</text></svg>'
        )
    """
    tools = await tools_for(tmp_path, texty)
    with pytest.raises(RenderFailed):
        await plugin(tmp_path).render(RenderRequest("x", {}), tools, LIMITS)
    data = manifest_data()
    data["svg_elements"] = ["text"]
    ok = CliPlugin(parse_manifest(data), tmp_path / "work")
    assert (await ok.render(RenderRequest("x", {}), tools, LIMITS)).svg.count("<text>") == 1


@runs_in_a_loop
async def test_a_tool_that_takes_too_long_is_stopped_and_that_is_said_in_words(tmp_path):
    slow = """
        import sys, time
        if "--version" in sys.argv:
            print("slow 1.0"); raise SystemExit(0)
        time.sleep(30)
    """
    with pytest.raises(RenderFailed, match="took longer"):
        await plugin(tmp_path).render(
            RenderRequest("x", {}), await tools_for(tmp_path, slow), Limits(seconds=1, memory_mb=512, output_mb=2)
        )


@runs_in_a_loop
async def test_a_tool_that_writes_no_picture_is_reported(tmp_path):
    silent = """
        import sys
        if "--version" in sys.argv:
            print("silent 1.0"); raise SystemExit(0)
    """
    with pytest.raises(RenderFailed, match="no picture"):
        await plugin(tmp_path).render(RenderRequest("x", {}), await tools_for(tmp_path, silent), LIMITS)


@runs_in_a_loop
async def test_the_job_folder_is_gone_afterwards(tmp_path):
    await plugin(tmp_path).render(RenderRequest("x", {}), await tools_for(tmp_path), LIMITS)
    assert list((tmp_path / "work").iterdir()) == []


@runs_in_a_loop
async def test_a_job_folder_has_a_short_path_however_deep_the_servers_work_folder_is(tmp_path):
    """Chromium refuses to start where a socket path (in its profile, in the job folder) passes 107 characters."""
    where = """
        import os, sys
        if "--version" in sys.argv:
            print("where 1.0"); raise SystemExit(0)
        open(sys.argv[2], "w").write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><desc>{os.getcwd()}</desc></svg>'
        )
    """
    deep = tmp_path / ("a-rather-long-folder-name-" * 4) / "plugins"
    result = await CliPlugin(parse_manifest(manifest_data()), deep).render(
        RenderRequest("x", {}), await tools_for(tmp_path, where), LIMITS
    )
    folder = result.svg.split("<desc>")[1].split("</desc>")[0]
    assert len(folder) <= 60 and not folder.startswith(str(deep))
