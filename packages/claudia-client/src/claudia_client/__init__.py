"""claudia-client: what every client of a Claudia server shares.

For now that is ``TlsPolicy``: which servers a client trusts over TLS, the way an SSH client trusts a host (the first
time the person is shown the server's fingerprint and decides; a different certificate later is refused loudly).
"""

from ._version import __version__
from .trust import TlsPolicy, UntrustedCertificate, fingerprint_of

__all__ = ["TlsPolicy", "UntrustedCertificate", "__version__", "fingerprint_of"]
