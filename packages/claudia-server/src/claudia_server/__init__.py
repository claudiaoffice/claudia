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
from .assistant import Assistant, AsyncEngine, Call, Engine, Say, Step, Task
from .auth import AI_USER, Account, AuthRefused, Credentials, ScryptDirectory, UserDirectory
from .certs import Certificate, CertificateError, ensure_certificate
from .composes import composes_methods
from .computes import computes_methods
from .creates import creates_methods, creates_methods_with
from .filestore import FileDirectory, FileProvider
from .heavy_dispatch import DEFAULT_TIMEOUT, HeavyDispatcher, Submittable
from .hub import Connection, DocumentProvider, HostedDocument, Hub, HubError, MemoryProvider, StoredInfo
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
    ServerSettings,
    TypesetSettings,
    load_admins,
    load_settings,
    save_admins,
    save_settings,
)
from .standin import ScriptedEngine
from .standin_text import TextEngine
from .workers import DEFAULT_MAX_WAITING, DEFAULT_WORKERS, PoolBusy, WorkerPool

__all__ = [
    "AI_USER",
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
    "Gateway",
    "HeavyDispatcher",
    "HostedDocument",
    "Hub",
    "HubError",
    "Limits",
    "MemoryProvider",
    "Method",
    "MethodTable",
    "ModelEngine",
    "PoolBusy",
    "Proposal",
    "RequestError",
    "Resolution",
    "RestoreCoordinator",
    "RestoreError",
    "Say",
    "ScriptedEngine",
    "SealedDocuments",
    "ServerSettings",
    "Step",
    "ScryptDirectory",
    "StoredInfo",
    "Submittable",
    "Task",
    "TextEngine",
    "TypesetSettings",
    "UserDirectory",
    "WorkerPool",
    "__version__",
    "admin_router",
    "composes_methods",
    "computes_methods",
    "core_methods",
    "create_app",
    "creates_methods",
    "creates_methods_with",
    "ensure_certificate",
    "load_admins",
    "load_settings",
    "methods_for",
    "model_assistant_for",
    "needs_administrator",
    "parse_request",
    "save_admins",
    "save_settings",
    "stand_in_assistant_for",
]
