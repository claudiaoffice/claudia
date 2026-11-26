"""A small Taiga REST client (standard library only) and the shared bits of the sync.

Credentials: ``TAIGA_USERNAME`` and ``TAIGA_PASSWORD`` from the environment; failing that, the ``taiga`` MCP server's
entry in ``~/.claude.json``. ``TAIGA_URL`` (default https://api.taiga.io) and ``TAIGA_PROJECT`` (default the
claudia-office project) can be overridden the same way.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent  # claudiaoffice-log
REPO = LOG.parent
PROJECT_DIR = LOG / "Projects" / "claudia-office"
TASKS = PROJECT_DIR / "_tasks"
PROJECT_MD = PROJECT_DIR / "claudia-office.md"
OPEN_MD = LOG / "bugtracker-open.md"
FIXED_MD = LOG / "bugtracker-fixed.md"
STATE = Path(__file__).resolve().parent / "sync-state.json"

LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def unlink(text: str) -> str:
    """``[[file|Shown]]`` -> ``Shown``; ``[[file]]`` -> ``file``."""
    return LINK.sub(lambda m: m.group(2) or m.group(1), text)


def fingerprint(value: object) -> str:
    return hashlib.sha1(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- footer: the "**Key:** value" block under "---"

FOOTER_SEP = "\n\n---\n\n"


def split_footer(description: str) -> tuple[str, dict[str, str]]:
    """A description as the exporters write it: the body, a rule, and ``**Key:** value`` lines."""
    description = (description or "").replace("\r\n", "\n")
    head, sep, tail = description.rpartition(FOOTER_SEP)
    if not sep and description.lstrip().startswith("**"):  # an empty body: the footer alone, without its rule
        head, sep, tail = "", "-", description
    if sep:
        lines = [line.rstrip() for line in tail.strip().split("\n")]
        fields = {}
        for line in lines:
            m = re.match(r"\*\*([^*]+):\*\* ?(.*)$", line)
            if not m:
                break
            fields[m.group(1).strip()] = m.group(2).strip()
        else:
            if "Source" in fields or "Tracker status" in fields or "Status in repo" in fields:
                return head.strip(), fields
    return description.strip(), {}


def join_footer(body: str, meta: list[tuple[str, str]]) -> str:
    footer = "  \n".join(f"**{k}:** {v}" for k, v in meta)
    return (body + FOOTER_SEP if body else "") + footer


# ---------------------------------------------------------------- Taiga


def _credentials() -> tuple[str, str, str, int]:
    url = os.environ.get("TAIGA_URL", "https://api.taiga.io")
    project = int(os.environ.get("TAIGA_PROJECT", "1816065"))
    user, password = os.environ.get("TAIGA_USERNAME"), os.environ.get("TAIGA_PASSWORD")
    if not (user and password):
        try:
            env = json.loads(Path("~/.claude.json").expanduser().read_text())["mcpServers"]["taiga"]["env"]
            user, password = env["TAIGA_USERNAME"], env["TAIGA_PASSWORD"]
            url = os.environ.get("TAIGA_URL", env.get("TAIGA_BASE_URL", url))
        except (OSError, KeyError, ValueError) as exc:
            raise SystemExit("set TAIGA_USERNAME and TAIGA_PASSWORD (no taiga entry in ~/.claude.json)") from exc
    return url.rstrip("/"), user, password, project


class Taiga:
    def __init__(self) -> None:
        url, user, password, self.project = _credentials()
        self.api = f"{url}/api/v1"
        self.token = None
        self.token = self.req("POST", "/auth", {"type": "normal", "username": user, "password": password})["auth_token"]
        proj = self.req("GET", f"/projects/{self.project}")
        self.us_status = {s["id"]: s["name"] for s in proj["us_statuses"]}
        self.epic_status = {s["id"]: s["name"] for s in proj["epic_statuses"]}
        self.issue_status = {s["id"]: s["name"] for s in proj["issue_statuses"]}
        self.priority = {s["id"]: s["name"] for s in proj["priorities"]}
        self.issue_type = {s["name"]: s["id"] for s in proj["issue_types"]}

    def req(self, method: str, path: str, body: dict | None = None, params: dict | None = None):
        url = self.api + path + ("?" + urllib.parse.urlencode(params) if params else "")
        headers = {"Content-Type": "application/json", "x-disable-pagination": "True",
                   "User-Agent": "claudia-taiga-sync"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                text = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{method} {path} -> {exc.code}: {exc.read()[:500]!r}") from exc
        return json.loads(text) if text else None

    def listing(self, kind: str) -> list[dict]:
        return self.req("GET", f"/{kind}", params={"project": self.project})

    @staticmethod
    def name_to_id(table: dict[int, str], name: str) -> int:
        return next(k for k, v in table.items() if v == name)

    # -- normalised views, the same shape the exporters produce from the repo

    def story_view(self, d: dict, epics_by_id: dict[int, str] | None = None) -> dict:
        epics = [e["subject"] for e in d.get("epics") or []]
        return {"subject": d["subject"], "status": self.us_status[d["status"]], "is_blocked": bool(d.get("is_blocked")),
                "description": d.get("description") or "", "tags": tag_names(d.get("tags")),
                "epic": epics[0].split()[0] if epics else None}

    def epic_view(self, d: dict) -> dict:
        return {"subject": d["subject"], "status": self.epic_status[d["status"]], "is_blocked": bool(d.get("is_blocked")),
                "description": d.get("description") or "", "tags": tag_names(d.get("tags")), "epic": None}

    def issue_view(self, d: dict) -> dict:
        return {"subject": d["subject"], "status": self.issue_status[d["status"]],
                "priority": self.priority[d["priority"]], "description": d.get("description") or "",
                "tags": tag_names(d.get("tags"))}


def tag_names(tags) -> list[str]:
    out = []
    for t in tags or []:
        out.append((t[0] if isinstance(t, (list, tuple)) else t).lower())
    return sorted(set(out))


# ---------------------------------------------------------------- state


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"items": {}}


def save_state(state: dict) -> None:
    """One item per line, sorted, so that two branches' syncs merge in git like any other text."""
    items = state["items"]
    lines = [f"  {json.dumps(k)}: {json.dumps(items[k], sort_keys=True, ensure_ascii=False)}" for k in sorted(items)]
    STATE.write_text('{"items": {\n' + ",\n".join(lines) + "\n}}\n", encoding="utf-8")
