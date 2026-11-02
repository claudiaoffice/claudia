"""claudia-container: the encrypted document file of Claudia (E2).

The building blocks of the file's security: the password rules (:mod:`claudia_container.passwords`), the
cryptographic primitives behind one small interface (:mod:`claudia_container.crypto`), the key slots that decide who may
open which part of a document (:mod:`claudia_container.slots`), the document file with its people
(:mod:`claudia_container.container`) and the encrypted journal of an open document (:mod:`claudia_container.journal`).
Packing the journal into encrypted blocks follows in a later version. The design is in the project document
``e2-container-design.md`` (decisions D70 to D82).
"""

from ._version import __version__
from .container import (
    FORMAT_TEXT,
    ContainerError,
    Manifest,
    NotAClaudiaDocument,
    Person,
    ReaderLimitExceeded,
    UnsupportedFormat,
    add_user,
    change_password,
    create_document,
    journal_path,
    read_manifest,
    read_people,
    remove_user,
    unlock,
    unlock_with_recovery,
)
from .crypto import (
    DecryptionError,
    KdfParams,
    LoginMaterial,
    derive_login_material,
    derive_recovery_material,
    open_sealed,
    random_key,
    seal,
)
from .journal import JournalError, JournalRecord, JournalWriter, read_journal
from .passwords import MIN_PASSWORD_LENGTH, WeakPassword, password_problems, require_strong_password
from .slots import (
    ROLE_DOMAINS,
    Domain,
    InvalidRecoveryKey,
    KeySlot,
    Role,
    Unlocked,
    format_recovery_key,
    make_slot,
    new_domain_keys,
    new_recovery_key,
    open_slot,
    parse_recovery_key,
)

__all__ = [
    "FORMAT_TEXT",
    "MIN_PASSWORD_LENGTH",
    "ROLE_DOMAINS",
    "ContainerError",
    "DecryptionError",
    "Domain",
    "InvalidRecoveryKey",
    "JournalError",
    "JournalRecord",
    "JournalWriter",
    "KdfParams",
    "KeySlot",
    "LoginMaterial",
    "Manifest",
    "NotAClaudiaDocument",
    "Person",
    "ReaderLimitExceeded",
    "Role",
    "Unlocked",
    "UnsupportedFormat",
    "WeakPassword",
    "__version__",
    "add_user",
    "change_password",
    "create_document",
    "derive_login_material",
    "derive_recovery_material",
    "format_recovery_key",
    "journal_path",
    "make_slot",
    "new_domain_keys",
    "new_recovery_key",
    "open_sealed",
    "open_slot",
    "parse_recovery_key",
    "password_problems",
    "random_key",
    "read_journal",
    "read_manifest",
    "read_people",
    "remove_user",
    "require_strong_password",
    "seal",
    "unlock",
    "unlock_with_recovery",
]
