"""Exit status 0 if the server in this container answers ``/api/health``.

The server is TLS by default with a certificate of its own, and plain HTTP with ``--no-tls``; both are tried.
The certificate is not verified: this only asks the server running in the same container.
"""

import http.client
import ssl
import sys
import urllib.request

PORT = 8765


def healthy(scheme: str) -> bool:
    """Whether the server answers its health check over ``scheme`` (``http`` or ``https``)."""
    context = None
    if scheme == "https":
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(f"{scheme}://127.0.0.1:{PORT}/api/health", timeout=3, context=context) as reply:
            return reply.status == 200
    except OSError, http.client.HTTPException:
        return False


if __name__ == "__main__":
    sys.exit(0 if healthy("https") or healthy("http") else 1)
