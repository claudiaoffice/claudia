"""The setup code: who may name a server's first administrator (SEC-12, D1370, D1371)."""

import os
import stat

import pytest

from claudia_server.setup_code import SetupCode, read_code, remove_code, write_code

ALPHABET = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")  # Crockford's base32


def test_a_code_is_twelve_characters_of_crockfords_base32_shown_in_groups_of_four():
    code = SetupCode.make()
    assert len(code.value) == 12
    assert set(code.value) <= ALPHABET
    shown = str(code)
    assert shown == "-".join((code.value[:4], code.value[4:8], code.value[8:]))


def test_every_code_is_new():
    assert len({SetupCode.make().value for _ in range(200)}) == 200


def test_case_dashes_spaces_and_the_look_alike_letters_do_not_matter():
    code = SetupCode("K7QM4TXR92HB")
    assert code.matches("K7QM-4TXR-92HB")
    assert code.matches("k7qm 4txr 92hb")
    assert code.matches("  k7qm-4txr-92hb\n")
    zero_one = SetupCode("0Q1M4TXR92HB")
    assert zero_one.matches("oqlm-4txr-92hb")  # O is 0 and L is 1
    assert zero_one.matches("OQIM4TXR92HB")  # I is 1 too


def test_anything_else_does_not_match():
    code = SetupCode("K7QM4TXR92HB")
    for wrong in ("K7QM4TXR92H8", "K7QM4TXR92H", "K7QM4TXR92HBB", "", "Ä7QM4TXR92HB", None, 12, ["K7QM4TXR92HB"]):
        assert not code.matches(wrong)


def test_a_code_is_only_made_of_the_alphabet():
    for bad in ("K7QM4TXR92H", "K7QM4TXR92HU", "k7qm4txr92hb"):
        with pytest.raises(ValueError):
            SetupCode(bad)


def test_the_file_holds_the_code_for_the_servers_account_only(tmp_path):
    code = SetupCode.make()
    write_code(tmp_path, code)
    path = tmp_path / "admin" / "setup-code"
    assert path.read_text(encoding="utf-8") == f"{code}\n"
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert read_code(tmp_path) == code


def test_reading_without_a_file_or_from_a_damaged_one_gives_nothing(tmp_path):
    assert read_code(tmp_path) is None
    (tmp_path / "admin").mkdir()
    (tmp_path / "admin" / "setup-code").write_text("not a code\n", encoding="utf-8")
    assert read_code(tmp_path) is None


def test_removing_the_file_twice_is_no_error(tmp_path):
    write_code(tmp_path, SetupCode.make())
    remove_code(tmp_path)
    remove_code(tmp_path)
    assert not (tmp_path / "admin" / "setup-code").exists()
