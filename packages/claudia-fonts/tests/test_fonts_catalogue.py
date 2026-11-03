"""The catalogue: what fonts this server has, and what it says about the ones it will not use (E3.3)."""

import json

from claudia_fonts import COLLECTION_FILE, Catalogue, Collection, CollectionRecord, Resolution
from claudia_fonts.testing import make_font

RECORD = CollectionRecord(name="Test", licence="OFL-1.1", redistributable=True)


def folder(tmp_path, name, *fonts, record=True):
    """A collection folder holding the given (file name, make_font arguments) fonts."""
    path = tmp_path / name
    path.mkdir()
    if record:
        data = {"format": 1, "name": name, "licence": "OFL-1.1", "redistributable": True}
        (path / COLLECTION_FILE).write_text(json.dumps(data), encoding="utf-8")
    for file_name, kwargs in fonts:
        make_font(path / file_name, **kwargs)
    return path


def test_fonts_of_all_collections_are_listed_by_family(tmp_path):
    one = folder(tmp_path, "one", ("a.ttf", {"family": "Alpha"}), ("b.ttf", {"family": "Beta"}))
    two = folder(tmp_path, "two", ("c.ttf", {"family": "Gamma"}))
    catalogue = Catalogue.from_folders([one, two])
    assert catalogue.families() == ("Alpha", "Beta", "Gamma")
    assert catalogue.problems == ()


def test_subfolders_are_searched_and_other_files_are_ignored(tmp_path):
    root = folder(tmp_path, "one", ("a.ttf", {"family": "Alpha"}))
    (root / "static").mkdir()
    make_font(root / "static" / "b.otf", "Beta")
    (root / "README.txt").write_text("hello", encoding="utf-8")
    catalogue = Catalogue.from_folders([root])
    assert catalogue.families() == ("Alpha", "Beta")
    assert catalogue.problems == ()


def test_a_folder_without_a_record_is_listed_as_a_problem_and_the_others_still_load(tmp_path):
    bare = folder(tmp_path, "bare", ("a.ttf", {"family": "Alpha"}), record=False)
    good = folder(tmp_path, "good", ("b.ttf", {"family": "Beta"}))
    catalogue = Catalogue.from_folders([bare, good])
    assert catalogue.families() == ("Beta",)
    [problem] = catalogue.problems
    assert problem.path == bare
    assert COLLECTION_FILE in problem.reason


def test_a_broken_font_is_a_problem_and_its_neighbours_still_load(tmp_path):
    root = folder(tmp_path, "one", ("a.ttf", {"family": "Alpha"}))
    (root / "broken.ttf").write_text("nope", encoding="utf-8")
    catalogue = Catalogue.from_folders([root])
    assert catalogue.families() == ("Alpha",)
    [problem] = catalogue.problems
    assert problem.path == root / "broken.ttf"


def test_a_font_that_forbids_embedding_is_a_problem(tmp_path):
    root = folder(tmp_path, "one", ("r.ttf", {"family": "Locked", "fs_type": 2}))
    catalogue = Catalogue.from_folders([root])
    assert catalogue.families() == ()
    assert "embedding" in catalogue.problems[0].reason


def test_a_later_collection_replaces_the_same_family_and_style(tmp_path):
    first = folder(tmp_path, "first", ("a.ttf", {"family": "Alpha", "version": "1.0"}))
    second = folder(tmp_path, "second", ("a.ttf", {"family": "Alpha", "version": "2.0"}))
    catalogue = Catalogue.from_folders([first, second])
    [font] = catalogue.fonts_of("Alpha")
    assert font.path == second / "a.ttf"


def test_the_font_that_was_replaced_is_listed_so_that_nobody_uses_it_by_accident(tmp_path):
    first = folder(tmp_path, "first", ("a.ttf", {"family": "Alpha", "version": "1.0"}))
    second = folder(tmp_path, "second", ("a.ttf", {"family": "Alpha", "version": "2.0"}))
    [problem] = Catalogue.from_folders([first, second]).problems
    assert problem.path == first / "a.ttf"
    assert "replaced" in problem.reason


def test_lookup_ignores_case_and_orders_by_weight_then_slant(tmp_path):
    root = folder(
        tmp_path,
        "one",
        ("bold.ttf", {"family": "Alpha", "style": "Bold", "weight": 700}),
        ("italic.ttf", {"family": "Alpha", "style": "Italic", "italic": True}),
        ("regular.ttf", {"family": "Alpha", "style": "Regular"}),
    )
    catalogue = Catalogue.from_folders([root])
    assert "alpha" in catalogue
    assert "Missing" not in catalogue
    assert [f.style for f in catalogue.fonts_of("ALPHA")] == ["Regular", "Italic", "Bold"]
    assert catalogue.fonts_of("Missing") == ()


def test_a_font_is_found_by_its_hash(tmp_path):
    root = folder(tmp_path, "one", ("a.ttf", {"family": "Alpha"}))
    catalogue = Catalogue.from_folders([root])
    [font] = catalogue.fonts()
    assert catalogue.by_hash(font.sha256) == font
    assert catalogue.by_hash("0" * 64) is None


def test_the_digest_follows_the_fonts_and_not_the_order_of_the_folders(tmp_path):
    one = folder(tmp_path, "one", ("a.ttf", {"family": "Alpha"}))
    two = folder(tmp_path, "two", ("b.ttf", {"family": "Beta"}))
    forward = Catalogue.from_folders([one, two]).digest
    backward = Catalogue.from_folders([two, one]).digest
    assert forward == backward
    assert Catalogue.from_folders([one]).digest != forward


def test_the_digest_changes_when_a_font_file_changes(tmp_path):
    root = folder(tmp_path, "one", ("a.ttf", {"family": "Alpha", "version": "1.0"}))
    before = Catalogue.from_folders([root]).digest
    make_font(root / "a.ttf", "Alpha", version="1.1")
    assert Catalogue.from_folders([root]).digest != before


def test_an_empty_catalogue_has_a_digest_too(tmp_path):
    assert Catalogue.from_collections([]).digest == Catalogue.from_collections([]).digest


def test_collections_can_be_given_directly_for_folders_that_are_not_ours_to_write_in(tmp_path):
    root = tmp_path / "system"
    root.mkdir()
    make_font(root / "a.ttf", "Alpha")
    catalogue = Catalogue.from_collections([Collection(root, RECORD)])
    assert catalogue.families() == ("Alpha",)


# -- substitutes --------------------------------------------------------------------------------------------------


def test_a_missing_family_is_replaced_by_its_metric_compatible_substitute_when_we_have_it(tmp_path):
    root = folder(tmp_path, "one", ("c.ttf", {"family": "Carlito"}))
    catalogue = Catalogue.from_folders([root])
    assert catalogue.resolve("Calibri") == Resolution("Calibri", "Carlito", substituted=True)
    lower = catalogue.resolve("calibri")
    assert (lower.requested, lower.provided, lower.substituted) == ("calibri", "Carlito", True)


def test_no_substitute_is_named_when_we_do_not_have_it(tmp_path):
    root = folder(tmp_path, "one", ("a.ttf", {"family": "Alpha"}))
    assert Catalogue.from_folders([root]).resolve("Calibri") == Resolution("Calibri", None, substituted=False)


def test_a_family_we_have_is_never_substituted(tmp_path):
    root = folder(tmp_path, "one", ("c.ttf", {"family": "Carlito"}), ("k.ttf", {"family": "Calibri"}))
    assert Catalogue.from_folders([root]).resolve("Calibri") == Resolution("Calibri", "Calibri", substituted=False)


def test_the_substitutes_can_be_changed(tmp_path):
    root = folder(tmp_path, "one", ("a.ttf", {"family": "Alpha"}))
    catalogue = Catalogue.from_folders([root], substitutions={"Garamond": "Alpha"})
    assert catalogue.resolve("Garamond").provided == "Alpha"
    assert catalogue.resolve("Calibri").provided is None


def test_the_built_in_table_covers_the_common_office_fonts():
    from claudia_fonts import DEFAULT_SUBSTITUTIONS

    assert DEFAULT_SUBSTITUTIONS["Arial"] == "Liberation Sans"
    assert DEFAULT_SUBSTITUTIONS["Times New Roman"] == "Liberation Serif"
    assert DEFAULT_SUBSTITUTIONS["Courier New"] == "Liberation Mono"
    assert DEFAULT_SUBSTITUTIONS["Calibri"] == "Carlito"
    assert DEFAULT_SUBSTITUTIONS["Cambria"] == "Caladea"
