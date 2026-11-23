"""claudia-server: the process that holds documents and lets people work on them together (E3.1).

``create_app(hub, directory)`` is the FastAPI application: one WebSocket per person and document (see
``claudia_server.app`` for the handshake and ``claudia_server.protocol`` for the methods and events), ``/api/health``
and ``/api/protocol``. ``python3 -m claudia_server`` starts one.
"""

from ._version import __version__
from .admin import AdminAccount, AdminDirectory, needs_administrator
from .admin_api import AdminContext, AiRuntime, admin_router
from .admin_sessions import AdminSession, AdminSessions
from .app import Gateway, create_app
from .apps import methods_for, model_assistant_for, stand_in_assistant_for
from .assistant import AiTurn, Assistant, AsyncEngine, Call, Engine, Say, Task
from .auth import AI_USER, Account, AuthRefused, Credentials, ScryptDirectory, UserDirectory, WarmableDirectory
from .certs import Certificate, CertificateError, ensure_certificate
from .composes import composes_methods
from .computes import computes_methods, computes_methods_with
from .creates import creates_methods, creates_methods_with
from .filestore import FileDirectory, FileProvider
from .folder_lock import FolderLock, FolderLocked
from .heavy_dispatch import DEFAULT_TIMEOUT, HeavyDispatcher, Submittable
from .help import HelpContentError, HelpLibrary, Topic, default_library, parse_topic
from .hub import Connection, DocumentProvider, HostedDocument, Hub, HubError, MemoryProvider, Room, StoredInfo
from .idle import IdleWatch
from .kdf_policy import KdfPolicy
from .login_throttle import LoginThrottle
from .model_engine import ModelEngine
from .protocol import (
    ERROR_CODES,
    EVENTS,
    PROTOCOL_VERSION,
    Limits,
    Method,
    MethodTable,
    RequestError,
    core_methods,
    parse_request,
)
from .restore import Proposal, Resolution, RestoreCoordinator, RestoreError
from .sealed import SealedDocuments
from .server_settings import (
    AiSettings,
    Changed,
    SecuritySettings,
    ServerSettings,
    TypesetSettings,
    load_admins,
    load_settings,
    save_admins,
    save_settings,
)
from .standin import ScriptedEngine
from .standin_text import TextEngine
from .suite import APP_MODELS, Module, Suite
from .workers import DEFAULT_MAX_WAITING, DEFAULT_WORKERS, PoolBusy, WorkerPool

__all__ = [
    "AI_USER",
    "APP_MODELS",
    "DEFAULT_MAX_WAITING",
    "DEFAULT_TIMEOUT",
    "DEFAULT_WORKERS",
    "ERROR_CODES",
    "EVENTS",
    "PROTOCOL_VERSION",
    "Account",
    "AdminAccount",
    "AdminContext",
    "AdminDirectory",
    "AdminSession",
    "AdminSessions",
    "AiRuntime",
    "AiSettings",
    "Assistant",
    "AsyncEngine",
    "AuthRefused",
    "Call",
    "Certificate",
    "CertificateError",
    "Changed",
    "Connection",
    "Credentials",
    "DocumentProvider",
    "Engine",
    "FileDirectory",
    "FileProvider",
    "FolderLock",
    "FolderLocked",
    "Gateway",
    "HeavyDispatcher",
    "HelpContentError",
    "HelpLibrary",
    "HostedDocument",
    "Hub",
    "HubError",
    "IdleWatch",
    "KdfPolicy",
    "LoginThrottle",
    "Limits",
    "MemoryProvider",
    "Method",
    "MethodTable",
    "ModelEngine",
    "Module",
    "PoolBusy",
    "Proposal",
    "RequestError",
    "Resolution",
    "RestoreCoordinator",
    "RestoreError",
    "Room",
    "Say",
    "ScriptedEngine",
    "SealedDocuments",
    "SecuritySettings",
    "ServerSettings",
    "AiTurn",
    "ScryptDirectory",
    "StoredInfo",
    "Suite",
    "Submittable",
    "Task",
    "TextEngine",
    "Topic",
    "TypesetSettings",
    "UserDirectory",
    "WarmableDirectory",
    "WorkerPool",
    "__version__",
    "admin_router",
    "composes_methods",
    "computes_methods",
    "computes_methods_with",
    "core_methods",
    "create_app",
    "creates_methods",
    "creates_methods_with",
    "default_library",
    "ensure_certificate",
    "load_admins",
    "load_settings",
    "methods_for",
    "model_assistant_for",
    "needs_administrator",
    "parse_request",
    "parse_topic",
    "save_admins",
    "save_settings",
    "stand_in_assistant_for",
]
