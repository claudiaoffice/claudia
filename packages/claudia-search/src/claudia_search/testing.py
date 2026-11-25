"""What the tests of a search's time budget need (PROC-66)."""

STOPPED_IN_TIME = 5.0
"""Seconds within which a search that ran out of time must have come back, in the tests of the time budget.

The risk those tests guard against is a pattern that never stops: on their texts, ``(?:a|aa)+!`` would backtrack for
longer than anybody lives. Any bound far below that catches it. A bound near the deadline (0.6 s for 0.2 s) measured
the machine as well: a busy runner took 0.7 s and failed a search that had stopped on time."""
