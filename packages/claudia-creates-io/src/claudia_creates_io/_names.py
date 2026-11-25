"""What a presentation file calls its slides and objects, as names of the document (CODE-25, D550): one namespace for
everything in a document, so two things a file calls the same are told apart as a name worked out is (``Note (2)``)."""

from __future__ import annotations

from claudia_core import MAX_THING_NAME, clean_name, distinct_name, name_problem


class FileNames:
    """The names a file gives, taken one after the other as the import meets them."""

    def __init__(self) -> None:
        self._taken: list[str] = []

    def take(self, said: str | None) -> str:
        """The name for what the file calls ``said``: ``""`` where it says nothing a name can be, else the name itself
        or, when something before it has it, the first free ``"<name> (<n>)"``."""
        name = clean_name((said or "")[:MAX_THING_NAME])
        if not name or name_problem(name) is not None:
            return ""
        name = distinct_name(name, self._taken)
        self._taken.append(name)
        return name
