import random

from claudia_core import Document, UndoConflict, UndoRefused
from claudia_core.testing import Insert, Remove, Replace


def random_command(rng: random.Random, length: int):
    kinds = ["insert"] + (["remove", "replace"] if length else [])
    kind = rng.choice(kinds)
    if kind == "insert":
        return Insert(rng.randint(0, length), rng.randint(1, 99))
    if kind == "remove":
        return Remove(rng.randrange(length))
    return Replace(rng.randrange(length), rng.randint(1, 99))


def random_session(doc: Document, seed: int, steps: int = 200, authors=("ana", "ben", "ai"), checkpoints=True):
    """A mixed history: edits, per-author undo/redo, batches, checkpoints."""
    from claudia_core import Batch

    rng = random.Random(seed)
    for _ in range(steps):
        who = rng.choice(authors)
        roll = rng.random()
        if roll < 0.60:
            doc.execute(random_command(rng, len(doc.model.items)), author=who)
        elif roll < 0.70:
            n = len(doc.model.items)
            doc.execute(Batch((random_command(rng, n), Insert(0, rng.randint(1, 9))), "pair"), author=who)
        elif roll < 0.83:
            try_step(doc.undo, who)
        elif roll < 0.93:
            try_step(doc.redo, who)
        elif checkpoints:
            doc.save_checkpoint(who)
    return doc


def histories_of(doc: Document, authors=("ana", "ben", "ai")):
    return {
        a: (
            doc.history_for(a).undo_label,
            doc.history_for(a).redo_label,
            doc.history_for(a).can_undo,
            doc.history_for(a).can_redo,
        )
        for a in authors
    }


def try_step(step, who):
    """An undo that would hurt a colleague's work is refused; that is a correct outcome, not an error."""
    try:
        return step(who)
    except (UndoConflict, UndoRefused):
        return None
