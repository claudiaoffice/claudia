"""How the AI is taught to work in an app: its persona and its recipes (E7.2, D1560–D1563).

Each app ships two Markdown files in its own package, next to its help: ``ai/persona.md`` (who the AI is there, a short
list) and ``ai/skills.md`` (recipes: how to do one kind of task with the app's requests). The server knows no recipe.
It finds the files of the app of a document, and gives a model only the recipes whose requests it may use, so that it is
never told how to do what it may not do.

The files are English and read by the model only; they are not in the catalogues. A recipe is a ``## title``, a
``Uses: request, request`` line and its words with one worked example. What stands before the first ``## `` is for the
people who write the file and is not shown to a model. The two files together may hold ``MAX_CHARACTERS``: a test, not a
cut at run time, so nobody wonders later why the end of a recipe is missing.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass
from importlib import resources

from claudia_core import DocumentModel

MAX_CHARACTERS = 6000  # persona and recipes of one app together (D1562)
FOLDER, PERSONA, SKILLS = "ai", "persona.md", "skills.md"
RECIPES_HEADING = "How to do common tasks (adapt the examples: do not copy their values):"

_USES = re.compile(r"Uses:[ \t]*(.*)")


@dataclass(frozen=True)
class Recipe:
    """One kind of task: its title, the requests it needs, and the words that teach it."""

    title: str
    uses: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class Guidance:
    """What one app teaches the AI: who it is there, and how to do the app's usual tasks."""

    persona: str = ""
    recipes: tuple[Recipe, ...] = ()

    def skills_for(self, offered: Collection[str]) -> str:
        """The recipes whose requests are all in ``offered``, in the order of the file, under one heading; empty when
        there is none. A request that is not offered to this asker (a viewer, a person who chose *suggest*) takes its
        recipe away: telling a model how to use it only invites a refused request."""
        usable = [recipe for recipe in self.recipes if set(recipe.uses) <= set(offered)]
        if not usable:
            return ""
        return "\n\n".join([RECIPES_HEADING, *(f"{recipe.title}: {recipe.text}" for recipe in usable)])

    def size(self) -> int:
        """Characters of the persona and all recipes: the number the size cap holds down."""
        return len(self.persona) + sum(len(recipe.title) + len(recipe.text) for recipe in self.recipes)


def parse_recipes(text: str) -> tuple[Recipe, ...]:
    """The recipes of a ``skills.md``. ``ValueError`` naming a recipe that has no ``Uses:`` line with a request."""
    recipes = []
    for block in re.split(r"^## +", text.replace("\r\n", "\n"), flags=re.MULTILINE)[1:]:
        title, _, body = block.partition("\n")
        title = title.strip()
        first, _, rest = body.lstrip("\n").partition("\n")
        found = _USES.fullmatch(first.strip())
        uses = tuple(name.strip() for name in found.group(1).split(",") if name.strip()) if found else ()
        if not uses:
            raise ValueError(f"the recipe {title!r} has no 'Uses:' line naming the requests it needs")
        recipes.append(Recipe(title, uses, rest.strip()))
    return tuple(recipes)


def load_guidance(model_cls: type[DocumentModel]) -> Guidance:
    """The guidance of the app of ``model_cls``, from the package the class lives in; a package without the files (a
    test's document model) gives none. A file that is malformed stops the server at start, not a person at night."""
    try:
        folder = resources.files(model_cls.__module__.split(".")[0]) / FOLDER
        persona, skills = folder / PERSONA, folder / SKILLS
        return Guidance(
            persona.read_text(encoding="utf-8").strip() if persona.is_file() else "",
            parse_recipes(skills.read_text(encoding="utf-8")) if skills.is_file() else (),
        )
    except (ModuleNotFoundError, NotADirectoryError):
        return Guidance()
