"""claudia-search: the search of all three apps (E1.12, E5.15, D281-D287).

What a person wants to find is described in one of three ways (plain text, the builder, a typed pattern) and compiled
to one :class:`CompiledSearch`; that runs on the ``regex`` package with a deadline on every call, so a pattern that
backtracks without end is stopped instead of holding up the server (SEC-18). The engine knows no app.

An app offers its texts with their places (:class:`Text`, ``at`` being the app's own) and gets back matches,
replacement plans and the texts left out, all named by the same ``at`` (CODE-18). The app turns a plan into its own
command.

Modules:

    engine       Query, CompiledSearch, Match: what to find, compiled and run on one text (was ``claudia_core.search``)
    scan         Text, scan and plan: running a search over the texts of a document, and planning a replacement
"""

from ._version import __version__
from .engine import (
    COMBINE,
    CONDITIONS,
    COUNTS,
    MAX_SECONDS,
    MODES,
    WHOLE,
    CompiledSearch,
    Condition,
    Match,
    Part,
    Query,
    SearchError,
    SearchTimeout,
)
from .scan import (
    MAX_LISTED,
    Change,
    Hit,
    LeftOut,
    Location,
    Plan,
    Refusal,
    Scan,
    Skip,
    Text,
    location_key,
    plan,
    scan,
)

__all__ = [
    "COMBINE",
    "CONDITIONS",
    "COUNTS",
    "MAX_LISTED",
    "MAX_SECONDS",
    "MODES",
    "WHOLE",
    "Change",
    "CompiledSearch",
    "Condition",
    "Hit",
    "LeftOut",
    "Location",
    "Match",
    "Part",
    "Plan",
    "Query",
    "Refusal",
    "Scan",
    "SearchError",
    "SearchTimeout",
    "Skip",
    "Text",
    "__version__",
    "location_key",
    "plan",
    "scan",
]
