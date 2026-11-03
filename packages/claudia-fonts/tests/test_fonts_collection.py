"""A collection is a folder of fonts with a licence record next to them (E3.3): no record, no fonts."""

import json

import pytest

from claudia_fonts import COLLECTION_FILE, Collection, CollectionRecord, RecordError


def write_record(folder, **overrides):
    data = {
        "format": 1,
        "name": "Test collection",
        "licence": "OFL-1.1",
        "redistributable": True,
        "source": "https://example.org/fonts",
        "version": "2.1",
    }
    data |= overrides
    data = {key: value for key, value in data.items() if value is not None}
    (folder / COLLECTION_FILE).write_text(json.dumps(data), encoding="utf-8")


def test_a_record_is_read_from_the_collection_file(tmp_path):
    write_record(tmp_path)
    collection = Collection.from_folder(tmp_path)
    assert collection.folder == tmp_path
    assert collection.record == CollectionRecord(
        name="Test collection",
        licence="OFL-1.1",
        redistributable=True,
        source="https://example.org/fonts",
        version="2.1",
    )


def test_source_and_version_are_optional(tmp_path):
    write_record(tmp_path, source=None, version=None)
    record = Collection.from_folder(tmp_path).record
    assert (record.source, record.version) == ("", "")


def test_a_folder_without_a_record_is_refused_and_the_message_names_the_file(tmp_path):
    with pytest.raises(RecordError, match=COLLECTION_FILE):
        Collection.from_folder(tmp_path)


@pytest.mark.parametrize("missing", ["name", "licence", "redistributable", "format"])
def test_the_licence_record_is_mandatory_in_every_part(tmp_path, missing):
    write_record(tmp_path, **{missing: None})
    with pytest.raises(RecordError, match=missing):
        Collection.from_folder(tmp_path)


def test_a_blank_licence_is_no_licence(tmp_path):
    write_record(tmp_path, licence="  ")
    with pytest.raises(RecordError, match="licence"):
        Collection.from_folder(tmp_path)


def test_whether_fonts_may_be_handed_out_must_be_a_real_yes_or_no(tmp_path):
    write_record(tmp_path, redistributable="yes")
    with pytest.raises(RecordError, match="redistributable"):
        Collection.from_folder(tmp_path)


def test_a_newer_format_than_this_version_knows_is_refused(tmp_path):
    write_record(tmp_path, format=2)
    with pytest.raises(RecordError, match="format"):
        Collection.from_folder(tmp_path)


def test_a_record_that_is_not_json_is_refused(tmp_path):
    (tmp_path / COLLECTION_FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(RecordError, match=COLLECTION_FILE):
        Collection.from_folder(tmp_path)


def test_a_record_that_is_not_an_object_is_refused(tmp_path):
    (tmp_path / COLLECTION_FILE).write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(RecordError, match="object"):
        Collection.from_folder(tmp_path)
