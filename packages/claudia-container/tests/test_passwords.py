"""The password rules of D79: at least 8 characters with capital letters, small letters and digits."""

import pytest

from claudia_container.passwords import MIN_PASSWORD_LENGTH, WeakPassword, password_problems, require_strong_password


def test_the_minimum_is_eight_characters():
    assert MIN_PASSWORD_LENGTH == 8


@pytest.mark.parametrize("password", ["Abcdefg1", "Correct-Horse-Battery-9", "Ünïcode9x", "ПарольПароль7"])
def test_good_passwords_have_no_problems(password):
    assert password_problems(password) == ()
    require_strong_password(password)


@pytest.mark.parametrize(
    ("password", "problems"),
    [
        ("Abc1", ("too_short",)),
        ("abcdefg1", ("no_capital",)),
        ("ABCDEFG1", ("no_small",)),
        ("Abcdefgh", ("no_digit",)),
        ("abcdefgh", ("no_capital", "no_digit")),
        ("", ("too_short", "no_capital", "no_small", "no_digit")),
        ("12345678", ("no_capital", "no_small")),
    ],
)
def test_every_missing_rule_is_named_by_a_code_the_interface_can_translate(password, problems):
    assert password_problems(password) == problems


def test_seven_characters_are_too_short_even_if_everything_else_is_there():
    assert password_problems("Abcdef1") == ("too_short",)


def test_length_counts_characters_not_bytes():
    assert password_problems("Ää1" + "b" * 5) == ()  # 8 characters, 11 bytes


def test_a_weak_password_is_refused_with_its_problems():
    with pytest.raises(WeakPassword) as info:
        require_strong_password("short")
    assert info.value.problems == ("too_short", "no_capital", "no_digit")


def test_a_password_made_only_of_spaces_and_symbols_is_weak():
    assert "no_small" in password_problems("        ")
