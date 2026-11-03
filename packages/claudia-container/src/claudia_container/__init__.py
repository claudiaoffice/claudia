"""claudia-container: the encrypted document file of Claudia (E2).

This first version holds the building blocks of the file's security: the password rules
(:mod:`claudia_container.passwords`), the cryptographic primitives behind one small interface
(:mod:`claudia_container.crypto`) and the key slots that decide who may open which part of a document
(:mod:`claudia_container.slots`). The zip file itself, the journal and the blocks follow in later versions. The design
is in the project document ``e2-container-design.md`` (decisions D70 to D82).
"""

from ._version import __version__
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
    "MIN_PASSWORD_LENGTH",
    "ROLE_DOMAINS",
    "DecryptionError",
    "Domain",
    "InvalidRecoveryKey",
    "KdfParams",
    "KeySlot",
    "LoginMaterial",
    "Role",
    "Unlocked",
    "WeakPassword",
    "__version__",
    "derive_login_material",
    "derive_recovery_material",
    "format_recovery_key",
    "make_slot",
    "new_domain_keys",
    "new_recovery_key",
    "open_slot",
    "open_sealed",
    "parse_recovery_key",
    "password_problems",
    "random_key",
    "require_strong_password",
    "seal",
]
