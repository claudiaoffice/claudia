"""How the AI is taught to work in an app: its persona and its skills (E7.2, D1560–D1563).

Each app ships two Markdown files in its own package, next to its help: ``ai/persona.md`` (who the AI is there) and
``ai/skills.md`` (skills: how to do one kind of task with the app's requests). The server knows no skill. It finds the
files of the app of a document, and gives a model only the skills whose requests it may use, so that it is never told
how to do what it may not do.

A skill is a ``## title``, a ``Uses: request, request`` line and its words with one worked example. What stands before
the first ``## `` is for the people who write the file and is not shown to a model. The size of both files is held down
by a test (D1562), not by a cut at run time, so nobody wonders later why the end of a skill is missing.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass
from importlib import resources

from claudia_core import DocumentModel

FOLDER, PERSONA, SKILLS = "ai", "persona.md", "skills.md"
SKILLS_HEADING = "How to do common tasks (adapt the examples: do not copy their values):"

_USES = re.compile(r"Uses:[ \t]*(.*)")


@dataclass(frozen=True)
class Skill:
    """One kind of task (a skill of the glossary): its title, the requests it needs, and the words that teach it."""

    title: str
    uses: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class Guidance:
    """What one app teaches the AI: who it is there, and how to do the app's usual tasks."""

    persona: str = ""
    skills: tuple[Skill, ...] = ()

    def skills_for(self, offered: Collection[str]) -> str:
        """The skills whose requests are all in ``offered``, in the order of the file, under one heading; empty when
        there is none. A request that is not offered to this asker (a viewer, a person who chose *suggest*) takes its
        skill away: telling a model how to use it only invites a refused request."""
        usable = [skill for skill in self.skills if set(skill.uses) <= set(offered)]
        if not usable:
            return ""
        return "\n\n".join([SKILLS_HEADING, *(f"{skill.title}: {skill.text}" for skill in usable)])


def parse_skills(text: str) -> tuple[Skill, ...]:
    """The skills of a ``skills.md``. ``ValueError`` naming a skill that has no ``Uses:`` line with a request."""
    skills = []
    for block in re.split(r"^## +", text.replace("\r\n", "\n"), flags=re.MULTILINE)[1:]:
        title, _, body = block.partition("\n")
        title = title.strip()
        first, _, rest = body.lstrip("\n").partition("\n")
        found = _USES.fullmatch(first.strip())
        uses = tuple(name.strip() for name in found.group(1).split(",") if name.strip()) if found else ()
        if not uses:
            raise ValueError(f"the skill {title!r} has no 'Uses:' line naming the requests it needs")
        skills.append(Skill(title, uses, rest.strip()))
    return tuple(skills)


def load_guidance(model_cls: type[DocumentModel]) -> Guidance:
    """The guidance of the app of ``model_cls``, from the package the class lives in; a package without the files (a
    test's document model) gives none. A file that is malformed stops the server at start, not a person at night."""
    try:
        folder = resources.files(model_cls.__module__.split(".")[0]) / FOLDER
        persona, skills = folder / PERSONA, folder / SKILLS
        return Guidance(
            persona.read_text(encoding="utf-8").strip() if persona.is_file() else "",
            parse_skills(skills.read_text(encoding="utf-8")) if skills.is_file() else (),
        )
    except (ModuleNotFoundError, NotADirectoryError):
        return Guidance()
