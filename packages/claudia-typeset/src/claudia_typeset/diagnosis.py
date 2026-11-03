"""Trying out an installation and saying what is wrong in words that tell a person what to do (E13)."""

import re
from dataclasses import dataclass

from .programs import HELP_TOPIC

_MISSING_PACKAGE = re.compile(r"File `(?P<name>[^'/\\]+?)\.(?:sty|cls)' not found")
_MISSING_FONT = re.compile(r'font "[^"]*" cannot be found|is not available on this server')


@dataclass(frozen=True)
class Step:
    """One thing that was tried: its name, whether it worked, what was found or went wrong, and what to do."""

    name: str
    ok: bool
    detail: str
    hint: str = ""


@dataclass(frozen=True)
class Diagnosis:
    """What `Typesetter.diagnose` found, step by step."""

    steps: tuple[Step, ...]

    @property
    def ok(self) -> bool:
        """Whether every step worked."""
        return all(step.ok for step in self.steps)


def hint_for(message: str) -> str:
    """What to do about a TeX or font error, or an empty text when we do not know (never a guess)."""
    package = _MISSING_PACKAGE.search(message)
    if package:
        name = package["name"]
        return (
            f"The TeX package '{name}' is not installed. With TeX Live run: tlmgr install {name} "
            f"(if that name is unknown, 'tlmgr search --global --file {name}.sty' tells which package has the file). "
            f"With MiKTeX open the MiKTeX Console, go to Packages and install '{name}'. Then try again."
        )
    if _MISSING_FONT.search(message):
        return (
            "The font is not in the font catalogue of this server. Add a font collection that has it "
            f"(help topic: {HELP_TOPIC})."
        )
    return ""
