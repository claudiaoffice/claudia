"""Redaction plans kept for a preview (D721): the state a redaction would leave, by an opaque token.

``redaction_plan`` works a redaction out on a scratch model and hands the person a token for it; the views then read
that state through ``as_planned`` exactly as a replay reads an earlier step through ``as_of``, so the preview is drawn
by the views the app already has. A few plans per document are kept for a while (a dialog stays open longer than a
replay step), and a token that is gone is answered with an error the client meets by asking for the plan again.
"""

from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from weakref import WeakKeyDictionary

from claudia_core import Document, DocumentModel

#: How many plans of one document are kept, and for how long.
KEPT_PLANS = 4
KEPT_SECONDS = 900.0

_plans: WeakKeyDictionary[Document, OrderedDict[str, tuple[float, DocumentModel]]] = WeakKeyDictionary()


def keep_plan(document: Document, model: DocumentModel) -> str:
    """Keep ``model`` (a plan's state after the redaction) for ``document`` and return the token that finds it."""
    plans = _fresh(document)
    token = secrets.token_urlsafe(12)
    plans[token] = (time.monotonic(), model)
    while len(plans) > KEPT_PLANS:
        plans.popitem(last=False)
    return token


def planned_state(document: Document, token: str) -> DocumentModel | None:
    """The state kept under ``token`` for ``document``, or ``None`` once it is gone (or was never there)."""
    found = _fresh(document).get(token)
    return None if found is None else found[1]


def _fresh(document: Document) -> OrderedDict[str, tuple[float, DocumentModel]]:
    plans = _plans.setdefault(document, OrderedDict())
    now = time.monotonic()
    for token in [t for t, (at, _m) in plans.items() if now - at > KEPT_SECONDS]:
        del plans[token]
    return plans
