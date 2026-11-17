"""Adding fonts to a server (E3.13 f, D1041): check first, then add; a collection is renamed or removed as a whole.

What the administrator sees on Server settings ▸ Fonts comes from here: what a file would become before anything on
the server changes, the record written with the collection (who may receive the fonts, the licence in words, who added
it and when), and the reasons a font is not used, as codes a page can put into words in any language."""

import io
import json
import zipfile

import pytest

from claudia_fonts import COLLECTION_FILE, Catalogue, Collection, CollectionRecord
from claudia_fonts.adding import (
    MAX_FILES,
    AddRefused,
    add_collection,
    check_files,
    remove_collection,
    rename_collection,
)
from claudia_fonts.testing import make_font


def font_bytes(tmp_path, name, family="House Sans", style="Regular", **kwargs):
    """``(name, bytes)`` of a small font made for the test, as an upload brings it."""
    made = tmp_path / "made"
    made.mkdir(exist_ok=True)
    return name, make_font(made / name, family, style, **kwargs).read_bytes()


def shipped(tmp_path, family="Inter", style="Regular"):
    folder = tmp_path / "shipped"
    folder.mkdir()
    (folder / COLLECTION_FILE).write_text(
        json.dumps({"format": 1, "name": "Shipped", "licence": "OFL-1.1", "redistributable": True})
    )
    make_font(folder / f"{family}-{style}.ttf", family, style)
    return Catalogue.from_folders([folder])


def verdicts(checks):
    return [(c.name, c.verdict, c.code) for c in checks]


def test_each_file_gets_a_line_and_nothing_is_written(tmp_path):
    files = [
        font_bytes(tmp_path, "House-Regular.ttf"),
        font_bytes(tmp_path, "House-Bold.ttf", style="Bold", weight=700),
    ]
    checks = check_files(files, Catalogue.from_collections([]))
    assert verdicts(checks) == [("House-Regular.ttf", "added", ""), ("House-Bold.ttf", "added", "")]
    assert [(c.family, c.style, c.outlines) for c in checks] == [
        ("House Sans", "Regular", "truetype"),
        ("House Sans", "Bold", "truetype"),
    ]


def test_a_font_that_forbids_embedding_is_left_out_with_its_reason(tmp_path):
    files = [font_bytes(tmp_path, "House-BoldItalic.ttf", style="Bold Italic", fs_type=2)]
    [check] = check_files(files, Catalogue.from_collections([]))
    assert (check.verdict, check.code, check.family, check.style) == (
        "left-out",
        "forbids-embedding",
        "House Sans",
        "Bold Italic",
    )
    assert check.detail == "2"


def test_a_file_that_is_no_font_is_left_out(tmp_path):
    [check] = check_files([("notes.ttf", b"not a font")], Catalogue.from_collections([]))
    assert (check.verdict, check.code) == ("left-out", "not-a-font")


def test_a_file_of_another_kind_is_left_out_by_its_name(tmp_path):
    [check] = check_files([("readme.txt", b"hello")], Catalogue.from_collections([]))
    assert (check.verdict, check.code) == ("left-out", "not-a-font-file")


def test_a_font_the_server_has_already_is_said_to_replace_it(tmp_path):
    catalogue = shipped(tmp_path)
    [check] = check_files([font_bytes(tmp_path, "Inter-Regular.ttf", "Inter", version="9.0")], catalogue)
    assert (check.verdict, check.code, check.detail) == ("added", "replaces", "Shipped")


def test_the_same_font_twice_is_added_once(tmp_path):
    name, data = font_bytes(tmp_path, "House-Regular.ttf")
    checks = check_files([(name, data), ("copy.ttf", data)], Catalogue.from_collections([]))
    assert verdicts(checks) == [("House-Regular.ttf", "added", ""), ("copy.ttf", "left-out", "duplicate")]


def test_the_fonts_in_a_zip_are_checked_one_by_one(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("fonts/House-Regular.ttf", font_bytes(tmp_path, "a.ttf")[1])
        archive.writestr("../../escape/House-Bold.ttf", font_bytes(tmp_path, "b.ttf", style="Bold")[1])
        archive.writestr("OFL.txt", "licence")
    checks = check_files([("house.zip", buffer.getvalue())], Catalogue.from_collections([]))
    assert verdicts(checks) == [("House-Regular.ttf", "added", ""), ("House-Bold.ttf", "added", "")]


def test_a_broken_zip_is_left_out(tmp_path):
    [check] = check_files([("house.zip", b"PK\x03\x04 broken")], Catalogue.from_collections([]))
    assert (check.verdict, check.code) == ("left-out", "not-a-zip")


def test_too_many_files_are_refused(tmp_path):
    name, data = font_bytes(tmp_path, "a.ttf")
    with pytest.raises(AddRefused):
        check_files([(f"{n}.ttf", data) for n in range(MAX_FILES + 1)], Catalogue.from_collections([]))


def test_a_licence_the_fonts_name_is_suggested(tmp_path):
    files = [font_bytes(tmp_path, "a.ttf", licence="This Font Software is licensed under the SIL Open Font License")]
    [check] = check_files(files, Catalogue.from_collections([]))
    assert check.licence == "OFL-1.1"


def test_adding_writes_the_usable_files_and_the_record(tmp_path):
    files = [font_bytes(tmp_path, "House-Regular.ttf"), font_bytes(tmp_path, "House-BI.ttf", fs_type=2, style="BI")]
    root = tmp_path / "added"
    folder = add_collection(
        root,
        files,
        Catalogue.from_collections([]),
        name="City house fonts",
        licence="Licensed to the City (contract 2024-117)",
        redistributable=False,
        added_by="anna",
        added="2026-11-16",
    )
    assert folder.parent == root and folder.name == "city-house-fonts"
    assert sorted(p.name for p in folder.iterdir()) == sorted([COLLECTION_FILE, "House-Regular.ttf"])
    record = Collection.from_folder(folder).record
    assert record == CollectionRecord(
        name="City house fonts",
        licence="Licensed to the City (contract 2024-117)",
        redistributable=False,
        added_by="anna",
        added="2026-11-16",
    )
    assert record.may_go == "this-server"
    assert Catalogue.from_folders([folder]).families() == ("House Sans",)


def test_adding_nothing_usable_is_refused_and_leaves_no_folder(tmp_path):
    root = tmp_path / "added"
    with pytest.raises(AddRefused):
        add_collection(
            root,
            [("x.ttf", b"no")],
            Catalogue.from_collections([]),
            name="Empty",
            licence="l",
            redistributable=True,
            added_by="anna",
            added="2026-11-16",
        )
    assert not root.exists() or list(root.iterdir()) == []


@pytest.mark.parametrize("field", ["name", "licence"])
def test_a_collection_needs_a_name_and_a_licence(tmp_path, field):
    arguments = {"name": "House", "licence": "OFL-1.1"} | {field: "  "}
    with pytest.raises(AddRefused):
        add_collection(
            tmp_path,
            [font_bytes(tmp_path, "a.ttf")],
            Catalogue.from_collections([]),
            redistributable=True,
            added_by="anna",
            added="2026-11-16",
            **arguments,
        )


def test_two_collections_of_the_same_name_get_two_folders(tmp_path):
    common = {"redistributable": True, "added_by": "anna", "added": "2026-11-16", "licence": "OFL-1.1"}
    one = add_collection(
        tmp_path, [font_bytes(tmp_path, "a.ttf")], Catalogue.from_collections([]), name="House", **common
    )
    two = add_collection(
        tmp_path,
        [font_bytes(tmp_path, "b.ttf", family="Other")],
        Catalogue.from_collections([]),
        name="House",
        **common,
    )
    assert (one.name, two.name) == ("house", "house-2")


def test_a_collection_is_renamed_in_its_record_only(tmp_path):
    folder = add_collection(
        tmp_path,
        [font_bytes(tmp_path, "a.ttf")],
        Catalogue.from_collections([]),
        name="House",
        licence="OFL-1.1",
        redistributable=True,
        added_by="anna",
        added="2026-11-16",
    )
    rename_collection(folder, "City fonts")
    record = Collection.from_folder(folder).record
    assert (folder.name, record.name, record.added_by) == ("house", "City fonts", "anna")
    with pytest.raises(AddRefused):
        rename_collection(folder, " ")


def test_a_collection_is_removed_with_its_files_but_only_inside_the_root(tmp_path):
    root = tmp_path / "added"
    folder = add_collection(
        root,
        [font_bytes(tmp_path, "a.ttf")],
        Catalogue.from_collections([]),
        name="House",
        licence="OFL-1.1",
        redistributable=True,
        added_by="anna",
        added="2026-11-16",
    )
    with pytest.raises(AddRefused):
        remove_collection(root, tmp_path / "made")
    remove_collection(root, folder)
    assert not folder.exists()


def test_a_format_1_record_without_added_fields_still_reads(tmp_path):
    (tmp_path / COLLECTION_FILE).write_text(
        json.dumps({"format": 1, "name": "Old", "licence": "OFL-1.1", "redistributable": True})
    )
    record = Collection.from_folder(tmp_path).record
    assert (record.added_by, record.added, record.may_go) == ("", "", "anywhere")


def test_a_line_is_plain_data_without_the_bytes(tmp_path):
    [check] = check_files([font_bytes(tmp_path, "a.ttf")], Catalogue.from_collections([]))
    data = check.to_data()
    assert "data" not in data and data["family"] == "House Sans" and data["verdict"] == "added"


def test_too_many_bytes_are_refused_in_a_zip_and_all_together(tmp_path, monkeypatch):
    name, data = font_bytes(tmp_path, "a.ttf")
    monkeypatch.setattr("claudia_fonts.adding.MAX_BYTES", len(data) - 1)
    with pytest.raises(AddRefused, match="MB"):
        check_files([(name, data)], Catalogue.from_collections([]))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.ttf", data)
    with pytest.raises(AddRefused, match="too large"):
        check_files([("fonts.zip", buffer.getvalue())], Catalogue.from_collections([]))


def test_files_of_the_same_name_or_with_a_wildcard_get_names_of_their_own(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("one/House.ttf", font_bytes(tmp_path, "r.ttf")[1])
        archive.writestr("two/House.ttf", font_bytes(tmp_path, "b.ttf", style="Bold")[1])
    files = [("fonts.zip", buffer.getvalue()), ("Wild*.ttf", font_bytes(tmp_path, "i.ttf", style="Italic")[1])]
    folder = add_collection(
        tmp_path / "added",
        files,
        Catalogue.from_collections([]),
        name="House",
        licence="OFL-1.1",
        redistributable=True,
        added_by="anna",
        added="2026-11-16",
    )
    assert sorted(p.name for p in folder.glob("*.ttf")) == ["House-2.ttf", "House.ttf", "Wild_-2.ttf"]
    assert len(Catalogue.from_folders([folder]).fonts()) == 3


def test_a_collection_that_cannot_be_written_leaves_nothing_behind(tmp_path, monkeypatch):
    def failing(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("claudia_fonts.adding.write_atomically", failing)
    root = tmp_path / "added"
    with pytest.raises(OSError, match="disk full"):
        add_collection(
            root,
            [font_bytes(tmp_path, "a.ttf")],
            Catalogue.from_collections([]),
            name="House",
            licence="OFL-1.1",
            redistributable=True,
            added_by="anna",
            added="2026-11-16",
        )
    assert list(root.iterdir()) == []
