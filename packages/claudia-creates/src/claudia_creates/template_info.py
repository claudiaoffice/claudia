"""What a template says about itself: its name, what it is for, and the language it is written in (E10.4, D1536).

A template is a presentation without slides; this note travels with its state, so that a file says what it is. A
presentation started from a template keeps a copy as the note of where it came from: nothing follows it."""

from __future__ import annotations

from dataclasses import dataclass

from claudia_core import LanguageError, Refusal, normalize_language

MAX_NAME = 80
MAX_PURPOSE = 400


@dataclass(frozen=True)
class TemplateInfo:
    """The name of a template (what a person looks for), what it is for, and its language as a BCP 47 tag. Each fits
    or the note is refused with a sentence, so that nothing odd reaches a list or a file."""

    name: str
    purpose: str
    language: str

    def __post_init__(self) -> None:
        name, purpose = self.name.strip(), self.purpose.strip()
        if not name:
            raise Refusal("a template needs a name")
        if len(name) > MAX_NAME:
            raise Refusal("the name of a template has at most {limit} letters", limit=MAX_NAME)
        if not purpose:
            raise Refusal("say what the template is for")
        if len(purpose) > MAX_PURPOSE:
            raise Refusal("what a template is for takes at most {limit} letters", limit=MAX_PURPOSE)
        try:
            language = normalize_language(self.language)
        except LanguageError:
            raise Refusal("the language of a template is a tag like en, de or en-GB") from None
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "purpose", purpose)
        object.__setattr__(self, "language", language)

    def to_data(self) -> dict:
        return {"name": self.name, "purpose": self.purpose, "language": self.language}

    @classmethod
    def from_data(cls, data: dict) -> TemplateInfo:
        return cls(data["name"], data["purpose"], data["language"])
