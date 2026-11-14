"""The three built-in container types against their real tools: what each one is peculiar about (D393-D395).

LaTeX is code behind an adapter, Typst a command line with a prefix and a package door to close, Mermaid a browser that
needs configuration files. If the plugin contract is right, all three look the same from the service. These tests skip
for a tool this machine does not have (CI has all of them)."""

import pytest
from conftest import needs, posix_only, runs_in_a_loop

from claudia_render import RenderFailed

pytestmark = posix_only
NS = "http://www.w3.org/2000/svg"


def test_the_built_in_registry_has_the_three_types(real_service):
    assert [p.manifest.type for p in real_service.plugins.plugins()] == ["latex", "mermaid", "typst"]


@runs_in_a_loop
async def test_all_three_are_described_the_same_way_with_hints_for_the_editor_and_the_ai(real_service):
    described = {one["type"]: one for one in await real_service.describe_types()}
    for one in described.values():
        assert one["editor"]["example"] and one["editor"]["ai_hint"] and one["tier"] == "static"
    assert [p["name"] for p in described["latex"]["params"]] == ["mode", "width_mm"]


# -- LaTeX ------------------------------------------------------------------------------------------------------------
@runs_in_a_loop
async def test_latex_sets_a_formula(real_service):
    done = await real_service.render("latex", r"\frac{a}{b} + x^2", {})
    assert (
        "<svg" in done.svg[:200] and done.width > 10 and done.height > 5 and done.renderer.startswith("latex 1.0.0 | ")
    )


@runs_in_a_loop
async def test_latex_says_where_the_formula_is_wrong(real_service):
    with pytest.raises(RenderFailed) as failed:
        await real_service.render("latex", "x\n\\unknowncommand", {})
    assert failed.value.diagnostics[0].line == 2 and "Undefined control sequence" in failed.value.diagnostics[0].message


@runs_in_a_loop
async def test_latex_cannot_read_a_file_of_the_server(real_service):
    with pytest.raises(RenderFailed):
        await real_service.render("latex", r"\input{/etc/passwd}", {"mode": "page"})


@runs_in_a_loop
async def test_latex_a_page_is_as_wide_as_asked(real_service):
    narrow = await real_service.render("latex", "A paragraph of text. " * 20, {"mode": "page", "width_mm": 60})
    wide = await real_service.render("latex", "A paragraph of text. " * 20, {"mode": "page", "width_mm": 160})
    assert narrow.width < wide.width and narrow.height > wide.height


# -- Typst ------------------------------------------------------------------------------------------------------------
@needs("typst")
@runs_in_a_loop
async def test_typst_sets_a_page_sized_to_its_content(real_service):
    done = await real_service.render("typst", "= Title\n\nSome *bold* text and $x^2 + y^2$.", {})
    assert "<svg" in done.svg[:200] and 30 < done.width < 700 and 20 < done.height < 300


@needs("typst")
@runs_in_a_loop
async def test_typst_errors_have_the_line_of_the_persons_text_not_of_the_page_setup(real_service):
    with pytest.raises(RenderFailed) as failed:
        await real_service.render("typst", "= Fine\n#unknown_thing", {})
    first = failed.value.diagnostics[0]
    assert (first.line, first.column) == (2, 1) and "unknown variable" in first.message


@needs("typst")
@runs_in_a_loop
async def test_typst_packages_are_refused_before_anything_runs(real_service):
    with pytest.raises(RenderFailed, match="packages are not available") as failed:
        await real_service.render("typst", 'ok\n#import "@preview/cetz:0.3.0": canvas', {})
    assert failed.value.diagnostics[0].line == 2


@needs("typst")
@runs_in_a_loop
@pytest.mark.parametrize(
    "code",
    ['#read("/etc/passwd")', '#include "/etc/hostname"', '#image("../../../etc/passwd")', '#read("../outside.txt")'],
)
async def test_typst_cannot_read_what_is_outside_its_job_folder(real_service, code):
    with pytest.raises(RenderFailed):
        await real_service.render("typst", code, {})


@needs("typst")
@runs_in_a_loop
async def test_typst_settings_change_the_picture(real_service):
    small = await real_service.render("typst", "Some text", {"font_size": 8})
    large = await real_service.render("typst", "Some text", {"font_size": 24})
    assert large.width > small.width


# -- Mermaid ----------------------------------------------------------------------------------------------------------
@needs("mermaid")
@runs_in_a_loop
async def test_mermaid_draws_a_flowchart_with_text_in_it(real_service):
    done = await real_service.render("mermaid", "flowchart LR\n  Idea --> Draft --> Done", {})
    assert "<text" in done.svg and "Draft" in done.svg and done.width > 100 and "<script" not in done.svg


@needs("mermaid")
@runs_in_a_loop
async def test_mermaid_says_on_which_line_the_diagram_is_wrong(real_service):
    with pytest.raises(RenderFailed) as failed:
        await real_service.render("mermaid", "flowchart LR\n  A --> B\n  C --> D[[[\n", {})
    assert failed.value.diagnostics[0].line == 3


@needs("mermaid")
@runs_in_a_loop
@pytest.mark.parametrize(
    "text",
    [
        'flowchart LR\n  A["<script>alert(1)</script>"] --> B',
        'flowchart LR\n  A["<img src=x onerror=alert(1)>"] --> B',
        "flowchart LR\n  A --> B\n  click A call alert()",
        'flowchart LR\n  A --> B\n  click A "javascript:alert(1)"',
        '%%{init: {"securityLevel": "loose"}}%%\nflowchart LR\n  A["<b>x</b>"] --> B',
    ],
)
async def test_mermaid_cannot_bring_active_content_into_the_picture(real_service, text):
    try:
        done = await real_service.render("mermaid", text, {})
    except RenderFailed:
        return  # refused is as good as clean
    lowered = done.svg.lower()
    assert (
        "<script" not in lowered and "onerror" not in lowered.replace("onerror=alert(1)&gt;", "") or "&lt;" in lowered
    )
    assert "<foreignobject" not in lowered and "javascript:" not in lowered and "<a " not in lowered


@needs("mermaid")
@runs_in_a_loop
async def test_mermaid_a_theme_changes_the_picture(real_service):
    plain = await real_service.render("mermaid", "flowchart LR\n  A --> B", {})
    dark = await real_service.render("mermaid", "flowchart LR\n  A --> B", {"theme": "dark"})
    assert plain.svg != dark.svg
