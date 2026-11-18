"""claudia-test-documents: the test-document catalogue's engine (D218).

The library itself -- the catalogue, the per-feature directories, their ``source.docx``/``spec.py`` pairs -- is
data, kept at the repo root in ``test-documents/``, not in this package. This package is the part that reads
that data and runs it: the three-tier check (``Case``, ``runner.run_case``), the per-format adapters, loading a
``spec.py`` safely, and the catalogue file's own load/save/select. ``scripts/run_test_documents.py`` is the CLI
built on top of it.

case       Case, Model
adapters   Adapter, ADAPTERS
loader     load_case
catalogue  Entry, load_catalogue, save_catalogue, select, record_run
corpus     CorpusResult, discover_corpus, run_corpus, run_corpus_file, summarize_corpus, write_corpus_report (a folder
of documents with no spec: the generic checks, for a corpus a person keeps outside the repository)
runner     RunResult, run_case
render     render_first_page, perceptual_difference, visual_diff (Tier 3; not imported by default -- Pillow
and ``soffice`` are only needed once ``--visual`` is actually used)
"""

from ._version import __version__
from .adapters import ADAPTERS, Adapter
from .case import Case, Model
from .catalogue import Entry, record_run, select
from .catalogue import load as load_catalogue
from .catalogue import save as save_catalogue
from .corpus import CorpusResult, run_corpus
from .corpus import discover as discover_corpus
from .corpus import run_file as run_corpus_file
from .corpus import summarize as summarize_corpus
from .corpus import write_report as write_corpus_report
from .loader import load_case
from .runner import RunResult, run_case

__all__ = [
    "__version__",
    "ADAPTERS",
    "Adapter",
    "Case",
    "CorpusResult",
    "Entry",
    "Model",
    "RunResult",
    "discover_corpus",
    "load_case",
    "load_catalogue",
    "record_run",
    "run_case",
    "run_corpus",
    "run_corpus_file",
    "save_catalogue",
    "select",
    "summarize_corpus",
    "write_corpus_report",
]
