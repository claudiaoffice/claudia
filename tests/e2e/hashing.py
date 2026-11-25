"""How hard a test server hashes passwords: as little as the settings allow (PROC-55's follow-up, D1267).

Shared by ``live.py`` (the servers of the pytest browser tests) and ``scripts/run_e2e.py`` (the servers of the Node
browser scripts). It imports the server's settings only when it is called, so that ``run_e2e.py`` keeps to the standard
library until it starts a server.
"""

from __future__ import annotations

from pathlib import Path


def lower_hashing_cost(state: Path) -> None:
    """Save, under the state folder ``state`` of a server not started yet, the lowest hashing target the settings allow,
    unless a test chose a target of its own; every other setting the test saved stays as it is."""
    from claudia_server.hub import DEFAULT_MAX_DOCUMENTS
    from claudia_server.kdf_policy import MIN_TARGET_SECONDS
    from claudia_server.server_settings import SecuritySettings, load_settings, save_settings

    settings = load_settings(state, default_max_documents=DEFAULT_MAX_DOCUMENTS)
    if settings.security.kdf_target_seconds == SecuritySettings().kdf_target_seconds:
        settings.security.kdf_target_seconds = MIN_TARGET_SECONDS
        save_settings(state, settings)
