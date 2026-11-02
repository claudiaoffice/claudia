"""claudia-server: the process that holds documents and lets people work on them together (E3.1).

``create_app(hub, directory)`` is the FastAPI application: one WebSocket per person and document (see
``claudia_server.app`` for the handshake and ``claudia_server.protocol`` for the methods and events), ``/api/health``
and ``/api/protocol``. ``python3 -m claudia_server`` starts one.
"""

from ._version import __version__
from .app import Gateway, create_app
from .apps import methods_for, model_assistant_for, stand_in_assistant_for
from .assistant import Assistant, AsyncEngine, Call, Engine, Say, Step, Task
from .auth import AI_USER, Account, AuthRefused, Credentials, ScryptDirectory, UserDirectory
from .certs import Certificate, CertificateError, ensure_certificate
from .computes import computes_methods
from .filestore import FileDirectory, FileProvider
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
from .standin import ScriptedEngine

__all__ = [
    "AI_USER",
    "ERROR_CODES",
    "EVENTS",
    "PROTOCOL_VERSION",
    "Account",
    "Assistant",
    "AsyncEngine",
    "AuthRefused",
    "Call",
    "Certificate",
    "CertificateError",
    "Connection",
    "Credentials",
    "DocumentProvider",
    "Engine",
    "FileDirectory",
    "FileProvider",
    "Gateway",
    "HostedDocument",
    "Hub",
    "HubError",
    "Limits",
    "MemoryProvider",
    "Method",
    "MethodTable",
    "ModelEngine",
    "RequestError",
    "Say",
    "ScriptedEngine",
    "Step",
    "ScryptDirectory",
    "StoredInfo",
    "Task",
    "UserDirectory",
    "__version__",
    "computes_methods",
    "core_methods",
    "create_app",
    "ensure_certificate",
    "methods_for",
    "model_assistant_for",
    "parse_request",
    "stand_in_assistant_for",
]
