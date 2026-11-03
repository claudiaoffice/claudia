"""claudia-core: the kernel shared by claudia composes, computes and creates.

    revision     Revision(branch, seq): ids that survive redaction and can branch
    commands     Command, Batch, registry with schema versions and upcasters
    model        DocumentModel: the interface each app implements; Snapshot
    context      what a command works with while it applies
    region       Region: presence, locks and AI edits written once
    presence     holds that move with the edits
    log          Entry and CommandLog: the source of truth
    replay       apply a log to a model, deterministically
    history      per-author undo built from the log
    messages     chat records and ephemeral messages (the three message classes)
    manifest     what a document requires from a server
    store        what the kernel needs from storage (implemented by E2)
    document     Document: ties it all together
    events       what a Document tells its subscribers
    css          the CSS a style may hold: a versioned allow-list, a validator, the text form of a style
    styles       StyleBook and the commands that change it (E1.10)

The kernel contains no spreadbook, text or slide code and does no I/O.
"""

from ._version import __version__
from .commands import (
    Batch,
    Checkpoint,
    Command,
    CommandRegistry,
    Redacted,
    Redaction,
    Restore,
    Switch,
    encode,
    new_registry,
)
from .context import Context
from .css import ALLOWED_CSS, CSS_VERSION, CssError, CssProblem, format_css, parse_css, validate_css
from .document import Applied, CheckpointInfo, Document, Line, environment_of
from .errors import (
    KernelError,
    MissingUpcaster,
    RedactionError,
    RegionHeld,
    ReplayError,
    RevisionMismatch,
    SchemaTooNew,
    StaleEdit,
    UndoConflict,
    UndoRefused,
    UnknownCommand,
)
from .events import (
    BranchSwitched,
    ChatPosted,
    CheckpointSaved,
    CommandApplied,
    EphemeralPublished,
    EventBus,
    HistoryChanged,
    Rebuilt,
    ResultsStale,
)
from .events import Redacted as RedactedEvent
from .history import History, Step
from .log import CommandLog, Entry
from .manifest import (
    Environment,
    FontRequirement,
    FunctionInfo,
    FunctionRequirement,
    Manifest,
    RequirementReport,
    Requirements,
    check,
)
from .messages import ChatRecord, Ephemeral, parse_chat
from .model import DocumentModel, Snapshot
from .presence import Hold, Presence
from .region import Region, transform
from .replay import replay
from .revision import MAIN, Branch, Revision
from .store import DocumentStore, MemoryStore
from .styles import ChangeStyle, CreateStyle, RemoveStyle, RenameStyle, StyleBook, StyleDef, StylesChanged

__all__ = [
    "__version__",
    "ALLOWED_CSS",
    "CSS_VERSION",
    "Applied",
    "Batch",
    "Branch",
    "BranchSwitched",
    "ChatPosted",
    "ChangeStyle",
    "ChatRecord",
    "Checkpoint",
    "CheckpointInfo",
    "CheckpointSaved",
    "Command",
    "CommandApplied",
    "CommandLog",
    "CommandRegistry",
    "Context",
    "CreateStyle",
    "CssError",
    "CssProblem",
    "Document",
    "DocumentModel",
    "DocumentStore",
    "Entry",
    "Environment",
    "Ephemeral",
    "EphemeralPublished",
    "EventBus",
    "FontRequirement",
    "FunctionInfo",
    "FunctionRequirement",
    "History",
    "HistoryChanged",
    "Hold",
    "KernelError",
    "Line",
    "MAIN",
    "Manifest",
    "MemoryStore",
    "MissingUpcaster",
    "Presence",
    "Rebuilt",
    "Redacted",
    "RedactedEvent",
    "Redaction",
    "RedactionError",
    "Region",
    "RegionHeld",
    "RemoveStyle",
    "RenameStyle",
    "ReplayError",
    "RequirementReport",
    "Requirements",
    "Restore",
    "ResultsStale",
    "Revision",
    "RevisionMismatch",
    "SchemaTooNew",
    "Snapshot",
    "StaleEdit",
    "Step",
    "StyleDef",
    "StyleBook",
    "StylesChanged",
    "Switch",
    "UndoConflict",
    "UndoRefused",
    "UnknownCommand",
    "check",
    "encode",
    "environment_of",
    "format_css",
    "new_registry",
    "parse_chat",
    "parse_css",
    "replay",
    "transform",
    "validate_css",
]
