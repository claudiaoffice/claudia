"""What a plugin says about itself, read from plain data and checked before anything is run (D341, D343).

A manifest is data an administrator drops into a folder, so nothing in it may run anything by itself: it names tools
the *server* has registered, and the way it asks them for a picture is a list of arguments, never a shell line."""

import pytest

from claudia_render import API_VERSION, Manifest, ManifestError, parse_manifest


def data(**changes) -> dict:
    base = {
        "api": API_VERSION,
        "type": "pikchr",
        "version": "1.2.0",
        "title": "Pikchr",
        "requires": [{"tool": "pikchr", "version_at_least": "1.0"}],
        "cli": {"argv": ["${tool.pikchr}", "--svg-only", "${input}"], "output": "stdout"},
    }
    return {**base, **changes}


def test_a_manifest_names_what_it_is_and_what_it_needs():
    manifest = parse_manifest(data())
    assert isinstance(manifest, Manifest)
    assert (manifest.type, manifest.version, manifest.title, manifest.tier) == ("pikchr", "1.2.0", "Pikchr", "static")
    assert [(r.tool, r.version_at_least) for r in manifest.requires] == [("pikchr", "1.0")]
    assert manifest.cli is not None and manifest.cli.output == "stdout"


def test_a_manifest_for_another_contract_version_is_refused_with_the_versions_named():
    with pytest.raises(ManifestError, match=r"api 2.*this server reads api 1"):
        parse_manifest(data(api=2))


@pytest.mark.parametrize("field", ["type", "version", "title"])
def test_the_identity_fields_are_required(field):
    broken = data()
    del broken[field]
    with pytest.raises(ManifestError, match=field):
        parse_manifest(broken)


@pytest.mark.parametrize("bad", ["Pikchr", "a b", "../x", "", "p" * 33])
def test_a_type_is_a_plain_lower_case_name(bad):
    with pytest.raises(ManifestError, match="type"):
        parse_manifest(data(type=bad))


def test_a_version_is_dotted_numbers():
    for bad in ("one", "1..2", "1.2.x", ""):
        with pytest.raises(ManifestError, match="version"):
            parse_manifest(data(version=bad))


def test_a_field_nobody_knows_is_refused_so_that_a_typo_is_not_silently_ignored():
    with pytest.raises(ManifestError, match="colour"):
        parse_manifest(data(colour="red"))


def test_a_manifest_that_is_not_a_mapping_is_refused():
    with pytest.raises(ManifestError, match="mapping"):
        parse_manifest(["not", "a", "manifest"])  # type: ignore[arg-type]


# -- the settings a person may choose --------------------------------------------------------------------------------
def with_param(**spec) -> dict:
    return data(params=[{"name": "scale", "type": "number", "default": 1, **spec}])


def test_a_setting_has_a_type_a_default_and_bounds():
    manifest = parse_manifest(with_param(minimum=0.5, maximum=4))
    (scale,) = manifest.params
    assert (scale.name, scale.type, scale.default, scale.minimum, scale.maximum) == ("scale", "number", 1, 0.5, 4)


def test_a_default_must_satisfy_its_own_setting():
    with pytest.raises(ManifestError, match="default"):
        parse_manifest(with_param(default=9, maximum=4))
    with pytest.raises(ManifestError, match="default"):
        parse_manifest(data(params=[{"name": "mode", "type": "string", "choices": ["a", "b"], "default": "c"}]))


def test_the_settings_are_checked_against_what_a_person_sends():
    manifest = parse_manifest(
        data(
            params=[
                {"name": "scale", "type": "number", "default": 1, "minimum": 0.5, "maximum": 4},
                {"name": "mode", "type": "string", "choices": ["fast", "exact"], "default": "fast"},
                {"name": "dark", "type": "boolean", "default": False},
                {"name": "dpi", "type": "integer", "default": 96},
            ]
        )
    )
    assert manifest.check_params({}) == {"scale": 1, "mode": "fast", "dark": False, "dpi": 96}
    assert manifest.check_params({"scale": 2, "mode": "exact"})["scale"] == 2
    for bad in (
        {"scale": 9},
        {"scale": "2"},
        {"mode": "slow"},
        {"dark": 1},
        {"dpi": 1.5},
        {"unknown": 1},
        {"scale": True},
    ):
        with pytest.raises(ValueError, match="setting"):
            manifest.check_params(bad)


def test_a_setting_of_a_kind_nobody_knows_is_refused():
    with pytest.raises(ManifestError, match="type"):
        parse_manifest(data(params=[{"name": "x", "type": "colour", "default": "red"}]))


def test_two_settings_cannot_share_a_name():
    two = [{"name": "x", "type": "integer", "default": 1}] * 2
    with pytest.raises(ManifestError, match="twice"):
        parse_manifest(data(params=two))


# -- how the tool is asked --------------------------------------------------------------------------------------------
def test_a_free_text_setting_cannot_become_an_argument_because_it_could_start_with_a_dash():
    free = [{"name": "title", "type": "string", "default": "x"}]
    cli = {"argv": ["${tool.pikchr}", "${param.title}", "${input}"], "output": "stdout"}
    with pytest.raises(ManifestError, match="choices"):
        parse_manifest(data(params=free, cli=cli))
    parse_manifest(data(params=free, cli={**cli, "argv": ["${tool.pikchr}", "${input}"]}))  # fine when not an argument


def test_an_argument_may_only_name_what_exists():
    for bad in ("${param.nothing}", "${tool.other}", "${shell}", "${tool.pikchr.}"):
        with pytest.raises(ManifestError, match="placeholder"):
            parse_manifest(data(cli={"argv": ["${tool.pikchr}", bad], "output": "stdout"}))


def test_the_first_argument_is_the_tool_and_a_manifest_must_not_run_anything_else():
    with pytest.raises(ManifestError, match="first argument"):
        parse_manifest(data(cli={"argv": ["/bin/sh", "-c", "x"], "output": "stdout"}))


def test_the_output_is_a_plain_file_name_in_the_job_folder_or_the_tools_stdout():
    for bad in ("../x.svg", "/etc/passwd", "a/b.svg", ""):
        with pytest.raises(ManifestError, match="output"):
            parse_manifest(data(cli={"argv": ["${tool.pikchr}"], "output": bad}))


def test_support_files_are_plain_names_with_structured_content():
    cli = {
        "argv": ["${tool.pikchr}", "${input}"],
        "output": "stdout",
        "files": {"config.json": {"theme": "${param.scale}"}},
    }
    manifest = parse_manifest(data(cli=cli, params=[{"name": "scale", "type": "number", "default": 1}]))
    assert manifest.cli is not None and "config.json" in manifest.cli.files
    bad = {**cli, "files": {"../config.json": {"a": 1}}}
    with pytest.raises(ManifestError, match="file name"):
        parse_manifest(data(cli=bad, params=[{"name": "scale", "type": "number", "default": 1}]))


def test_a_diagnostics_reader_is_one_the_server_has():
    with pytest.raises(ManifestError, match="diagnostics"):
        parse_manifest(data(cli={"argv": ["${tool.pikchr}"], "output": "stdout", "diagnostics": "magic"}))


def test_a_manifest_without_a_way_to_render_needs_a_built_in_adapter():
    manifest = parse_manifest(data(cli=None, adapter="latex"))
    assert manifest.cli is None and manifest.adapter == "latex"
    with pytest.raises(ManifestError, match="cli or an adapter"):
        parse_manifest(data(cli=None))
    with pytest.raises(ManifestError, match="not both"):
        parse_manifest(data(adapter="latex"))


# -- the rest: limits, the SVG it draws, hints for the editor and the AI ----------------------------------------------
def test_the_limits_and_the_extra_svg_elements_have_safe_defaults():
    manifest = parse_manifest(data())
    assert manifest.svg_elements == frozenset()
    assert (manifest.limits.seconds, manifest.limits.address_space) == (20.0, True)


def test_a_plugin_may_ask_for_more_time_and_for_no_address_space_limit_but_the_server_has_the_last_word():
    manifest = parse_manifest(data(limits={"seconds": 60, "memory_mb": 4096, "address_space": False}))
    assert (manifest.limits.seconds, manifest.limits.memory_mb, manifest.limits.address_space) == (60, 4096, False)


def test_a_plugin_cannot_ask_for_elements_that_run_code():
    with pytest.raises(ManifestError, match="never allowed"):
        parse_manifest(data(svg_elements=["text", "script"]))


def test_hints_for_the_editor_and_the_ai_are_short_text():
    manifest = parse_manifest(data(editor={"syntax": "pikchr", "example": "box", "ai_hint": "Draw with boxes."}))
    assert (manifest.editor.syntax, manifest.editor.example, manifest.editor.ai_hint) == (
        "pikchr",
        "box",
        "Draw with boxes.",
    )
    with pytest.raises(ManifestError, match="ai_hint"):
        parse_manifest(data(editor={"ai_hint": "x" * 2001}))


def test_a_manifest_describes_itself_as_plain_data_for_the_clients_and_the_ai():
    shown = parse_manifest(data(params=[{"name": "scale", "type": "number", "default": 1}])).to_data()
    assert shown["type"] == "pikchr" and shown["params"][0]["name"] == "scale"
    assert "cli" not in shown, "how the tool is run is the server's business, not a client's"


# -- text the plugin refuses before anything runs -------------------------------------------------------------------
def test_a_plugin_may_name_patterns_that_make_a_text_unacceptable():
    manifest = parse_manifest(data(forbid=[{"pattern": r'"@[a-z]+/', "message": "packages are not available"}]))
    assert manifest.forbid[0].message == "packages are not available"
    assert manifest.forbid[0].matches('#import "@preview/x:1"') is not None
    assert manifest.forbid[0].matches("plain") is None


@pytest.mark.parametrize(
    "forbid",
    [
        [{"pattern": "(", "message": "x"}],  # not a regular expression
        [{"pattern": "a" * 201, "message": "x"}],
        [{"pattern": "a"}],  # no message
        [{"pattern": "a", "message": "x", "other": 1}],
        "a",
    ],
)
def test_a_pattern_that_is_not_one_is_refused(forbid):
    with pytest.raises(ManifestError, match="forbid"):
        parse_manifest(data(forbid=forbid))
