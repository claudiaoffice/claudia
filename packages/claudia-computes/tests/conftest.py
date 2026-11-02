import pytest

from claudia_computes import AddSheet, WorkbookModel
from claudia_core import CommandLog, Document, MemoryStore
from claudia_core.testing import FakeClock

S1 = "s1"


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def doc(clock):
    d = Document(WorkbookModel(), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)
    d.execute(AddSheet(S1, "Sheet1"), author="ana")
    return d


def reopen(doc):
    """A second document built from a copy of the log, to compare with the live one."""
    return Document.open(WorkbookModel, CommandLog.from_data(doc.log.to_data(), WorkbookModel.registry))
