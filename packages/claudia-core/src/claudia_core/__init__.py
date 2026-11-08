"""claudia-core: the kernel shared by claudia composes, computes and creates.

    assets       ImageAsset and ImageImport: the image model every app's objects can hold (E10.8)
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
    paragraphs   Paragraph and Run: styled text and who wrote which part, shared by all three apps (E10.17)
    shapes       ShapeDefinition: one outline in a 100 by 100 box, the same format in all three apps (E10.7)
    objects      the shared object layer: ObjectBody, Anchor, VisualObject, ObjectModel and their commands (E10.16)

The kernel contains no spreadbook, text or slide code and does no I/O.
"""

from ._version import __version__
from .assets import (
    MAX_IMAGE_BYTES,
    SUPPORTED_IMAGE_FORMATS,
    ImageAsset,
    ImageError,
    ImageImport,
    decode_image,
)
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
from .objects import (
    ASPECT_TOLERANCE,
    MAX_OBJECTS_PER_CONTAINER,
    MAX_SELECTION,
    MIN_OBJECT_SIZE,
    OBJECT_KINDS,
    AddObject,
    Anchor,
    DefineImage,
    DefineShape,
    ForgetImage,
    ForgetShape,
    ImagesChanged,
    MoveObject,
    ObjectBody,
    ObjectModel,
    ObjectsChanged,
    ObjectSet,
    RemoveObject,
    ResizeObject,
    RotateObject,
    SetParagraph,
    SetParagraphStyle,
    SetSnap,
    SetText,
    ShapesChanged,
    VisualObject,
    paragraph_for,
)
from .paragraphs import (
    MAX_PARAGRAPH_TEXT,
    Paragraph,
    Run,
    delete_runs,
    insert_runs,
    normalized,
    runs_from_data,
    runs_to_data,
    slice_runs,
    total,
)
from .presence import Hold, Presence
from .region import Region, transform
from .replay import replay
from .revision import MAIN, Branch, Revision
from .shapes import BOX, FORMAT, ShapeDefinition, ShapeError, parse_shape
from .store import DocumentStore, MemoryStore
from .styles import ChangeStyle, CreateStyle, RemoveStyle, RenameStyle, StyleBook, StyleDef, StylesChanged

__all__ = [
    "__version__",
    "AddObject",
    "ALLOWED_CSS",
    "Anchor",
    "Applied",
    "ASPECT_TOLERANCE",
    "Batch",
    "BOX",
    "Branch",
    "BranchSwitched",
    "ChangeStyle",
    "ChatPosted",
    "ChatRecord",
    "check",
    "Checkpoint",
    "CheckpointInfo",
    "CheckpointSaved",
    "Command",
    "CommandApplied",
    "CommandLog",
    "CommandRegistry",
    "Context",
    "CreateStyle",
    "CSS_VERSION",
    "CssError",
    "CssProblem",
    "decode_image",
    "DefineImage",
    "DefineShape",
    "delete_runs",
    "Document",
    "DocumentModel",
    "DocumentStore",
    "encode",
    "Entry",
    "Environment",
    "environment_of",
    "Ephemeral",
    "EphemeralPublished",
    "EventBus",
    "FontRequirement",
    "ForgetImage",
    "ForgetShape",
    "FORMAT",
    "format_css",
    "FunctionInfo",
    "FunctionRequirement",
    "History",
    "HistoryChanged",
    "Hold",
    "ImageAsset",
    "ImageError",
    "ImageImport",
    "ImagesChanged",
    "insert_runs",
    "KernelError",
    "Line",
    "MAIN",
    "Manifest",
    "MAX_IMAGE_BYTES",
    "MAX_OBJECTS_PER_CONTAINER",
    "MAX_PARAGRAPH_TEXT",
    "MAX_SELECTION",
    "MemoryStore",
    "MIN_OBJECT_SIZE",
    "MissingUpcaster",
    "MoveObject",
    "new_registry",
    "normalized",
    "OBJECT_KINDS",
    "ObjectBody",
    "ObjectModel",
    "ObjectsChanged",
    "ObjectSet",
    "Paragraph",
    "paragraph_for",
    "parse_chat",
    "parse_css",
    "parse_shape",
    "Presence",
    "Rebuilt",
    "Redacted",
    "RedactedEvent",
    "Redaction",
    "RedactionError",
    "Region",
    "RegionHeld",
    "RemoveObject",
    "RemoveStyle",
    "RenameStyle",
    "replay",
    "ReplayError",
    "RequirementReport",
    "Requirements",
    "ResizeObject",
    "Restore",
    "ResultsStale",
    "Revision",
    "RevisionMismatch",
    "RotateObject",
    "Run",
    "runs_from_data",
    "runs_to_data",
    "SchemaTooNew",
    "SetParagraph",
    "SetParagraphStyle",
    "SetSnap",
    "SetText",
    "ShapeDefinition",
    "ShapeError",
    "ShapesChanged",
    "slice_runs",
    "Snapshot",
    "StaleEdit",
    "Step",
    "StyleBook",
    "StyleDef",
    "StylesChanged",
    "SUPPORTED_IMAGE_FORMATS",
    "Switch",
    "total",
    "transform",
    "UndoConflict",
    "UndoRefused",
    "UnknownCommand",
    "validate_css",
    "VisualObject",
]
