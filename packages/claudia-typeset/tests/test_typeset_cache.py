"""Typeset results are kept by what they were made from, so the same formula is never set twice (E3.4)."""

import pytest

from claudia_typeset import Job, Mode, ResultCache, cache_key

ENGINE = "XeTeX 3.14"


def key(job, **changes):
    arguments = {"engine": ENGINE, "fonts": "digest-1"} | changes
    return cache_key(job, **arguments)


def test_the_same_job_has_the_same_key():
    assert key(Job(Mode.MATH, "x^2")) == key(Job(Mode.MATH, "x^2"))


@pytest.mark.parametrize(
    "other",
    [
        Job(Mode.MATH, "x^3"),
        Job(Mode.PAGE, "x^2"),
        Job(Mode.PAGE, "x^2", width_mm=100),
        Job(Mode.MATH, "x^2", font="Liberation Serif"),
    ],
)
def test_anything_that_changes_the_picture_changes_the_key(other):
    assert key(other) != key(Job(Mode.MATH, "x^2"))


def test_another_engine_or_another_font_collection_changes_the_key():
    job = Job(Mode.MATH, "x^2")
    assert key(job, engine="XeTeX 3.15") != key(job)
    assert key(job, fonts="digest-2") != key(job)


def test_the_key_is_safe_to_use_as_a_file_name():
    assert len(key(Job(Mode.MATH, "../../etc/passwd"))) == 64
    assert key(Job(Mode.MATH, "../../etc/passwd")).isalnum()


def test_a_missing_result_is_none(tmp_path):
    assert ResultCache(tmp_path / "cache").get("a" * 64) is None


def test_a_stored_result_comes_back(tmp_path):
    cache = ResultCache(tmp_path / "cache")
    cache.put("a" * 64, "<svg/>")
    assert cache.get("a" * 64) == "<svg/>"


def test_a_result_survives_a_new_cache_on_the_same_folder(tmp_path):
    ResultCache(tmp_path).put("b" * 64, "<svg/>")
    assert ResultCache(tmp_path).get("b" * 64) == "<svg/>"


def test_a_key_that_is_not_a_digest_is_refused(tmp_path):
    cache = ResultCache(tmp_path)
    for bad in ("../x", "short", "A" * 64, "g" * 64):
        with pytest.raises(ValueError, match="key"):
            cache.get(bad)
        with pytest.raises(ValueError, match="key"):
            cache.put(bad, "<svg/>")


def test_a_half_written_file_is_never_seen(tmp_path):
    cache = ResultCache(tmp_path)
    cache.put("c" * 64, "<svg/>")
    assert [path.name for path in tmp_path.iterdir()] == ["c" * 64 + ".svg"]


def test_a_result_that_cannot_be_read_back_as_text_counts_as_missing(tmp_path):
    cache = ResultCache(tmp_path)
    (tmp_path / ("d" * 64 + ".svg")).write_bytes(b"\xff\xfe\x00bad")
    assert cache.get("d" * 64) is None
