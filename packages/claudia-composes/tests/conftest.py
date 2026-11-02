import pytest
from composes_helpers import SENTENCE

from claudia_composes import InsertText, TextModel
from claudia_core import Document, MemoryStore
from claudia_core.testing import FakeClock


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def doc(clock):
    """A document whose only paragraph (``b1``) holds a sentence that ann wrote."""
    d = Document(TextModel(), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)
    d.execute(InsertText("b1", 0, SENTENCE), author="ann")
    return d
