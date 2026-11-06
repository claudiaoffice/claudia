"""The password rules of D109: at least 8 characters, with capital letters, small letters and digits.

The rules return *codes* instead of sentences, so the interface can translate them (E5.7). Length counts characters
after Unicode normalisation (NFKC), the same form that is later used to derive the key.
"""

import unicodedata

MIN_PASSWORD_LENGTH = 8
"""Shortest allowed password. One named constant, so it can be raised in one place."""


class WeakPassword(ValueError):
    """A password broke the rules; ``problems`` lists the codes.

    The codes are ``too_short``, ``no_capital``, ``no_small`` and ``no_digit``.
    """

    def __init__(self, problems: tuple[str, ...]) -> None:
        super().__init__("the password is too weak: " + ", ".join(problems))
        self.problems = problems


def password_problems(password: str) -> tuple[str, ...]:
    """The rules this password breaks, as codes in a fixed order; an empty tuple means it is allowed."""
    text = unicodedata.normalize("NFKC", password)
    problems = []
    if len(text) < MIN_PASSWORD_LENGTH:
        problems.append("too_short")
    if not any(c.isupper() for c in text):
        problems.append("no_capital")
    if not any(c.islower() for c in text):
        problems.append("no_small")
    if not any(c.isdecimal() for c in text):
        problems.append("no_digit")
    return tuple(problems)


def require_strong_password(password: str) -> None:
    """Raise :class:`WeakPassword` if the password breaks a rule. Used at creation and at every password change."""
    problems = password_problems(password)
    if problems:
        raise WeakPassword(problems)
