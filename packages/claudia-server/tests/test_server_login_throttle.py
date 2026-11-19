"""Failed logins wait longer each time, per address and per document and name; nobody is locked out (D1266, SEC-11).

``LoginThrottle`` is a plain class with an injected clock: no sockets, no sleeping.
"""

import pytest

from claudia_core.testing import FakeClock
from claudia_server.login_throttle import LoginThrottle

ADDRESS, DOC, NAME = "203.0.113.7", "plan", "ann"


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def throttle(clock):
    return LoginThrottle(clock=clock.lock_time)


def fail(throttle, times=1, *, address=ADDRESS, doc=DOC, name=NAME):
    for _ in range(times):
        throttle.failed(address, doc, name)


def test_nobody_waits_before_a_failure(throttle):
    assert throttle.check(ADDRESS, DOC, NAME) == 0


def test_the_first_three_failures_are_free(throttle):
    for _ in range(3):
        assert throttle.check(ADDRESS, DOC, NAME) == 0
        fail(throttle)
    assert throttle.check(ADDRESS, DOC, NAME) == 0


@pytest.mark.parametrize(("failures", "wait"), [(4, 1), (5, 2), (6, 4), (7, 8), (8, 10)])
def test_then_one_two_four_eight_seconds_and_for_one_document_and_name_never_more_than_ten(throttle, failures, wait):
    # a different address each time, so that only the (document, name) counts
    for i in range(failures):
        fail(throttle, address=f"198.51.100.{i}")
    assert throttle.check("192.0.2.1", DOC, NAME) == wait


def test_one_address_waits_longer_each_time_up_to_thirty_seconds(throttle):
    waits = []
    for i in range(10):
        fail(throttle, name=f"name-{i}")  # a new name each time: only the address counts
        waits.append(throttle.check(ADDRESS, DOC, "somebody else"))
    assert waits == [0, 0, 0, 1, 2, 4, 8, 16, 30, 30]


def test_the_wait_runs_out_with_time(throttle, clock):
    fail(throttle, 4)
    assert throttle.check(ADDRESS, DOC, NAME) == 1
    clock.advance(0.4)
    assert throttle.check(ADDRESS, DOC, NAME) == pytest.approx(0.6)
    clock.advance(0.7)
    assert throttle.check(ADDRESS, DOC, NAME) == 0


def test_a_failure_after_the_wait_is_over_makes_the_next_wait_longer(throttle, clock):
    fail(throttle, 4)
    clock.advance(1.1)
    fail(throttle)
    assert throttle.check(ADDRESS, DOC, NAME) == 2


def test_a_stranger_who_keeps_guessing_a_name_delays_her_by_ten_seconds_at_most(throttle, clock):
    for i in range(200):
        fail(throttle, address=f"198.51.{i // 250}.{i % 250}")
    assert throttle.check("192.0.2.99", DOC, NAME) == 10, "the owner from another address waits ten seconds"
    clock.advance(10.01)
    assert throttle.check("192.0.2.99", DOC, NAME) == 0, "and is let in after that: nothing is locked"


def test_a_success_from_an_address_clears_what_it_had_failed(throttle):
    fail(throttle, 5, name="x")
    assert throttle.check(ADDRESS, DOC, "y") == 2
    throttle.succeeded(ADDRESS)
    assert throttle.check(ADDRESS, DOC, "y") == 0


def test_a_success_does_not_clear_the_failures_against_a_name(throttle):
    """Else anybody could reset a name's counter by logging in somewhere else, and guess for free."""
    for i in range(5):
        fail(throttle, address=f"198.51.100.{i}")
    throttle.succeeded("192.0.2.1")
    assert throttle.check("192.0.2.2", DOC, NAME) == 2


def test_the_counters_forget_after_fifteen_minutes_without_a_failure(throttle, clock):
    fail(throttle, 8)
    clock.advance(14 * 60)
    assert throttle.check(ADDRESS, DOC, NAME) == 0
    fail(throttle)
    clock.advance(15 * 60 + 1)
    fail(throttle)  # the old failures are forgotten: this is the first again
    assert throttle.check(ADDRESS, DOC, NAME) == 0


def test_a_name_that_does_not_exist_counts_like_one_that_does(throttle, clock):
    """The answer must tell nothing about which documents and names there are (D50, SEC-04)."""
    other = LoginThrottle(clock=clock.lock_time)
    fail(throttle, 6, doc="exists", name="ann")
    fail(other, 6, doc="no-such-document", name="nobody")
    assert throttle.check(ADDRESS, "exists", "ann") == other.check(ADDRESS, "no-such-document", "nobody")


def test_a_name_is_counted_the_way_names_are_compared(throttle):
    for i in range(5):
        fail(throttle, address=f"198.51.100.{i}", name="Ann ")
    assert throttle.check("192.0.2.1", DOC, "ann") == 2, "capitals and spaces do not make a new name"


def test_the_document_is_part_of_the_key(throttle):
    for i in range(5):
        fail(throttle, address=f"198.51.100.{i}", doc="plan")
    assert throttle.check("192.0.2.1", "other", NAME) == 0


def test_what_is_remembered_is_bounded_and_the_oldest_quiet_entries_go_first(clock):
    small = LoginThrottle(clock=clock.lock_time, max_entries=50)
    for i in range(500):
        small.failed(f"198.51.{i // 250}.{i % 250}", DOC, f"name-{i}")
        clock.advance(0.001)
    assert small.size() <= 100, "50 addresses and 50 names at most"
    small.failed("192.0.2.1", DOC, "last")
    assert small.size() <= 100


def test_the_limits_can_be_set(clock):
    strict = LoginThrottle(clock=clock.lock_time, free_tries=0, address_cap=5.0, name_cap=3.0)
    strict.failed(ADDRESS, DOC, NAME)
    assert strict.check(ADDRESS, DOC, NAME) == 1
    for _ in range(10):
        strict.failed(ADDRESS, DOC, NAME)
    assert strict.check(ADDRESS, DOC, NAME) == 5


@pytest.mark.parametrize("bad", [{"free_tries": -1}, {"address_cap": 0}, {"name_cap": -1}, {"max_entries": 0}])
def test_a_limit_that_makes_no_sense_is_refused(bad):
    with pytest.raises(ValueError):
        LoginThrottle(**bad)


def test_a_name_that_is_not_text_is_still_counted(throttle):
    for _ in range(5):
        throttle.failed(ADDRESS, DOC, None)
    assert throttle.check(ADDRESS, DOC, 12) == 2, "all the same address: the address counts, whatever it typed"
