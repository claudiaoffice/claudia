"""E1.9: what a document requires from a server, checked on open."""

from typing import ClassVar

from claudia_core import (
    Document,
    Environment,
    FontRequirement,
    FunctionInfo,
    FunctionRequirement,
    Manifest,
    Requirements,
    ResultsStale,
    check,
    environment_of,
)
from claudia_core.testing import FakeClock, Insert, ListModel


class Needy(ListModel):
    app: ClassVar[str] = "test-list"

    def __init__(self, items=None):
        super().__init__(items)
        self.stale = []

    def requirements(self):
        return Requirements(
            (FunctionRequirement("xnpv", "2", "aaaa1111"), FunctionRequirement("fit", "1", "bbbb2222")),
            (FontRequirement("Inter"), FontRequirement("Carlito"), FontRequirement("Secret Sans")),
        )

    def mark_stale(self, functions):
        self.stale += list(functions)


def make():
    clock = FakeClock()
    doc = Document(Needy(), clock=clock.time)
    doc.execute(Insert(0, 1))
    return doc


def env(**kw):
    functions = {"xnpv": FunctionInfo("2", "aaaa1111"), "fit": FunctionInfo("1", "bbbb2222")}
    base = environment_of(Needy, functions=functions, fonts={"Inter", "Carlito", "Secret Sans"})
    return Environment(**{**base.__dict__, **kw})


def test_manifest_lists_app_schemas_functions_and_fonts():
    manifest = make().manifest()
    assert manifest.app == "test-list" and manifest.command_schemas == {"list.Insert": 1}
    assert [f.name for f in manifest.requirements.functions] == ["xnpv", "fit"]
    assert Manifest.from_data(manifest.to_data()) == manifest


def test_everything_present_is_clean():
    report = make().check_requirements(env())
    assert report.ok and report.clean and report.describe() == []


def test_a_missing_function_blocks_with_a_precise_message():
    report = make().check_requirements(env(functions={"fit": FunctionInfo("1", "bbbb2222")}))
    assert not report.ok and report.missing_functions == ("xnpv",)
    assert report.describe() == ["Function xnpv is not installed."]


def test_a_changed_digest_marks_results_stale_but_does_not_block():
    doc = make()
    changed = {"xnpv": FunctionInfo("2", "ffff9999"), "fit": FunctionInfo("1", "bbbb2222")}
    report = doc.check_requirements(env(functions=changed))
    assert report.ok and not report.clean and report.stale_names == ("xnpv",)
    seen = []
    doc.subscribe(lambda e: seen.append(e) if isinstance(e, ResultsStale) else None)
    doc.apply_report(report)
    assert doc.model.stale == ["xnpv"] and seen[0].functions == ("xnpv",)


def test_fonts_are_offered_or_reported_unavailable():
    report = make().check_requirements(env(fonts=frozenset({"Inter"}), providable_fonts=frozenset({"Carlito"})))
    assert report.fonts_to_provide == ("Carlito",) and report.fonts_unavailable == ("Secret Sans",)
    assert report.ok  # a missing font never prevents opening
    assert any("Carlito" in line for line in report.describe())


def test_other_app_and_newer_schemas_block():
    manifest = make().manifest()
    assert check(manifest, env(app="other")).wrong_app == "test-list"
    newer = Manifest(manifest.app, manifest.state_schema + 1, {"list.Insert": 5, "ext.x.Y": 1}, manifest.requirements)
    report = check(newer, env())
    assert report.state_too_new and report.unknown_commands == ("ext.x.Y",)
    assert report.commands_too_new == (("list.Insert", 5, 1),)
    assert not report.ok and len(report.describe()) == 3
