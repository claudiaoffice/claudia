"""The setup that lets a typesetting engine use the collection, and nothing else (E3.3, E3.4)."""

import json
import sys
from xml.etree import ElementTree

import pytest

from claudia_fonts import COLLECTION_FILE, Catalogue, write_fontconfig
from claudia_fonts.testing import make_font


def collection_folder(tmp_path, name, *fonts, record=True):
    path = tmp_path / name
    path.mkdir()
    if record:
        data = {"format": 1, "name": name, "licence": "OFL-1.1", "redistributable": True}
        (path / COLLECTION_FILE).write_text(json.dumps(data), encoding="utf-8")
    for file_name, kwargs in fonts:
        make_font(path / file_name, **kwargs)
    return path


def config_of(tmp_path, *folders, name="job"):
    directory = tmp_path / name
    directory.mkdir(exist_ok=True)
    job = write_fontconfig(Catalogue.from_folders(folders), directory, tmp_path / "fccache")
    return job, ElementTree.parse(job.config).getroot()


def test_the_config_is_written_in_the_given_folder_and_the_environment_names_it(tmp_path):
    folder = collection_folder(tmp_path, "one", ("a.ttf", {"family": "Alpha"}))
    job, _ = config_of(tmp_path, folder)
    assert job.config == tmp_path / "job" / "fonts.conf"
    assert job.environment == {"FONTCONFIG_FILE": str(job.config)}


def test_each_folder_that_holds_fonts_is_listed_once(tmp_path):
    one = collection_folder(tmp_path, "one", ("a.ttf", {"family": "Alpha"}), ("b.ttf", {"family": "Beta"}))
    two = collection_folder(tmp_path, "two", ("c.ttf", {"family": "Gamma"}))
    _, root = config_of(tmp_path, one, two)
    assert [d.text for d in root.findall("dir")] == [str(one), str(two)]


def test_the_system_fonts_are_not_included(tmp_path):
    """The engine sees the collection and nothing else: no include of the system's own configuration."""
    folder = collection_folder(tmp_path, "one", ("a.ttf", {"family": "Alpha"}))
    _, root = config_of(tmp_path, folder)
    assert root.find("include") is None


def test_the_cache_folder_is_the_one_given(tmp_path):
    folder = collection_folder(tmp_path, "one", ("a.ttf", {"family": "Alpha"}))
    _, root = config_of(tmp_path, folder)
    assert root.findtext("cachedir") == str(tmp_path / "fccache")


def test_a_font_the_catalogue_refused_is_hidden_from_the_engine_by_name(tmp_path):
    folder = collection_folder(
        tmp_path, "one", ("a.ttf", {"family": "Alpha"}), ("locked.ttf", {"family": "Locked", "fs_type": 2})
    )
    _, root = config_of(tmp_path, folder)
    assert [g.text for g in root.findall("selectfont/rejectfont/glob")] == [str(folder / "locked.ttf")]


def test_a_font_that_a_later_collection_replaced_is_hidden_so_the_engine_uses_the_same_one_as_the_browser(tmp_path):
    first = collection_folder(tmp_path, "first", ("a.ttf", {"family": "Alpha", "version": "1.0"}))
    second = collection_folder(tmp_path, "second", ("a.ttf", {"family": "Alpha", "version": "2.0"}))
    _, root = config_of(tmp_path, first, second)
    assert [g.text for g in root.findall("selectfont/rejectfont/glob")] == [str(first / "a.ttf")]


def test_a_folder_the_catalogue_refused_is_not_listed_and_has_nothing_to_hide(tmp_path):
    good = collection_folder(tmp_path, "good", ("a.ttf", {"family": "Alpha"}))
    bare = collection_folder(tmp_path, "bare", ("b.ttf", {"family": "Beta"}), record=False)
    _, root = config_of(tmp_path, good, bare)
    assert [d.text for d in root.findall("dir")] == [str(good)]
    assert root.findall("selectfont/rejectfont/glob") == []


def test_a_folder_with_only_refused_fonts_is_not_listed(tmp_path):
    folder = collection_folder(tmp_path, "one", ("locked.ttf", {"family": "Locked", "fs_type": 2}))
    _, root = config_of(tmp_path, folder)
    assert root.findall("dir") == []


@pytest.mark.skipif(sys.platform == "win32", reason="Windows does not allow these characters in file names")
def test_special_characters_in_a_path_stay_valid_xml_and_come_back_unchanged(tmp_path):
    folder = collection_folder(tmp_path, "fonts <&> 'x'", ("a.ttf", {"family": "Alpha"}))
    _, root = config_of(tmp_path, folder)
    assert [d.text for d in root.findall("dir")] == [str(folder)]


def test_an_empty_catalogue_gives_a_config_with_no_fonts(tmp_path):
    _, root = config_of(tmp_path)
    assert root.findall("dir") == []
    assert root.findtext("cachedir") == str(tmp_path / "fccache")
