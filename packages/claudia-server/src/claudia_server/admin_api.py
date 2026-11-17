"""``/api/admin/*``: the server settings pages, and nothing else (E3.1, D5x).

Everything here is about the *server* — who may configure it and what it is configured to do — never about a
document; a document's own protocol (``app.py``) does not call into this module and this module does not call into
it. Every route but ``status``, ``setup`` and ``login`` needs a current administrator session
(``Authorization: Bearer <token>``, issued by ``login`` or ``setup``); :func:`admin_router` is the one way in.

``AdminContext`` is everything the routes need that is not already on the ``Suite``: the administrators themselves,
their sessions, the server's settings, where to persist both, whether this server is exposed beyond this computer
(decided once, at bind time, from the already-existing ``is_loopback`` signal: see ``cli.py``), and ``AiRuntime`` for
the one setting that is more than a value to remember — changing the AI model restarts the model itself (see
:meth:`AiRuntime.apply`). The one thing it does *not* carry is a way to change the access secret: that belongs to the
``Gateway`` that ``create_app`` builds, so ``admin_router`` takes it as a plain function instead (there is no other
reason for this module to know what a ``Gateway`` is)."""

import asyncio
import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from claudia_ai import ModelError, ModelRunner, OpenVinoModel
from claudia_core import DocumentModel
from claudia_core.clock import utc_now
from claudia_typeset.programs import EngineUnavailable, resolve_program

from .admin import AdminAccount, AdminDirectory, needs_administrator
from .admin_fonts import font_admin_routes
from .admin_sessions import AdminSessions
from .apps import model_assistant_for, stand_in_assistant_for
from .assistant import Assistant
from .fonts import FontService
from .server_settings import AiSettings, ServerSettings, TypesetSettings, save_admins, save_settings
from .suite import Suite

JsonBody = Annotated[dict, Body()]


def assistants_for(
    models: Iterable[type[DocumentModel]], runner: ModelRunner | None
) -> dict[str, Callable[[], Assistant] | None]:
    """Who answers ``@ai`` in each app, by app: with a ``runner``, the language model in every app that has a lens for
    it (one model for all of them, D432) and the scripted stand-in in the others; without one, the stand-in
    everywhere (``None`` for an app that has none)."""
    found: dict[str, Callable[[], Assistant] | None] = {}
    for model in models:
        factory = model_assistant_for(model, runner) if runner is not None else None
        found[model.app] = factory if factory is not None else stand_in_assistant_for(model)
    return found


def any_lens(models: Iterable[type[DocumentModel]], runner: ModelRunner) -> bool:
    """Can the language model of ``runner`` work in at least one of these apps?"""
    return any(model_assistant_for(model, runner) is not None for model in models)


@dataclass
class AiRuntime:
    """Where the admin API finds, and changes, the AI user's language model while the server runs.

    ``enabled`` is ``False`` for a server started with ``--no-assistant``: an operator's own decision that the
    settings pages must not be able to undo. ``models`` are the document models of the server's apps — the
    model-driven assistant is described to the language model in their terms (``apps.model_assistant_for``); one
    model serves all of them (D432)."""

    models: tuple[type[DocumentModel], ...]
    enabled: bool
    runner: ModelRunner | None = None

    async def apply(self, suite: Suite, settings: AiSettings) -> None:
        """Make ``settings`` the AI user's configuration in every app of ``suite``, from now on: later-opened
        documents get it; documents already open keep whichever assistant they were opened with (the same way a
        changed ``max_documents`` only ever bounds documents opened after it changed). Closes the model this replaces,
        if there was one.

        ``ValueError`` if the AI is disabled for this server, the model cannot be loaded, or none of this server's apps
        has an assistant for it."""
        if not self.enabled:
            raise ValueError("the AI assistant is disabled for this server (it was started with --no-assistant)")
        old_runner = self.runner
        runner = None if settings.model_dir is None else await self._load(settings.model_dir, settings)
        for app, factory in assistants_for(self.models, runner).items():
            module = suite.module(app)
            if module is not None:
                module.hub.assistant = factory
        self.runner = runner
        if old_runner is not None:
            old_runner.close()

    async def _load(self, model_dir: str, settings: AiSettings) -> ModelRunner:
        try:
            runner = await asyncio.to_thread(
                lambda: ModelRunner(
                    OpenVinoModel(model_dir, settings.device),
                    max_new_tokens=settings.max_tokens,
                    timeout=settings.timeout,
                )
            )
        except ModelError as exc:
            raise ValueError(str(exc)) from exc
        if not any_lens(self.models, runner):
            runner.close()
            raise ValueError("this server's document model has no AI assistant yet")
        return runner


@dataclass
class AdminContext:
    """Everything the admin API needs besides the ``Suite`` itself."""

    admins: AdminDirectory
    sessions: AdminSessions
    settings: ServerSettings
    state_dir: Path
    ai: AiRuntime
    exposed: bool
    fonts: FontService | None = None
    """The server's fonts, for Server settings ▸ Fonts (``admin_fonts``); ``None`` for a server without them."""


def _bearer_token(request: Request) -> str | None:
    scheme, _, token = (request.headers.get("authorization") or "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else None


def _account_dict(account: AdminAccount, *, signed_in_as: str) -> dict:
    return {"name": account.name, "added": account.added, "you": account.name == signed_in_as}


def _diagnose_typeset(typeset: TypesetSettings) -> dict[str, dict]:
    """Whether ``xelatex`` and ``pdftocairo`` can be found as ``typeset`` configures them, right now. Cheap: this
    only looks at the file system and the ``PATH``, it does not run either program."""
    result: dict[str, dict] = {}
    for setting, value in (("xelatex", typeset.xelatex), ("pdftocairo", typeset.pdftocairo)):
        try:
            program = resolve_program(setting, value, setting)
        except EngineUnavailable as exc:
            result[setting] = {"ok": False, "detail": str(exc)}
        else:
            result[setting] = {"ok": True, "detail": str(program)}
    return result


def _identity_routes(router: APIRouter, context: AdminContext, require_admin: Callable) -> None:
    """``status``, ``setup``, ``login``, ``logout``, ``me``: becoming and being an administrator."""
    Signedin = Annotated[str, Depends(require_admin)]

    @router.get("/status")
    async def status():
        """Public: whether this server needs somebody to become its first administrator (``exposed`` and nobody
        is one yet). A settings page checks this before anything else, since it decides what to show.

        ``administrator`` is the earliest-added administrator's name, or ``null`` if there is none yet — a hint a
        client can turn into a friendly label ("<name>'s server") before anyone has signed in to this server in
        this browser; it carries no authority and nothing here requires a session."""
        needs = needs_administrator(context.exposed, len(context.admins))
        first = context.admins.list_admins()
        return {
            "needs_administrator": needs,
            "exposed": context.exposed,
            "administrator": first[0].name if first else None,
        }

    @router.post("/setup")
    async def setup(body: JsonBody):
        """Become this server's first administrator. Refused once it has one — sign in and add another instead."""
        if len(context.admins) > 0:
            raise HTTPException(409, "this server already has an administrator; sign in to add another")
        name, password = body.get("name"), body.get("password")
        if not (isinstance(name, str) and isinstance(password, str)):
            raise HTTPException(400, "a name and a password are needed")
        try:
            account = await asyncio.to_thread(context.admins.add, name, password, added=utc_now())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        save_admins(context.state_dir, context.admins)
        token = context.sessions.issue(account.name)
        return {"token": token, "admin": _account_dict(account, signed_in_as=account.name)}

    @router.post("/login")
    async def login(body: JsonBody):
        """Sign in as an existing administrator."""
        name, password = body.get("name"), body.get("password")
        account = await asyncio.to_thread(context.admins.verify, name, password)
        if account is None:
            raise HTTPException(401, "wrong name or password")
        token = context.sessions.issue(account.name)
        return {"token": token, "admin": _account_dict(account, signed_in_as=account.name)}

    @router.post("/logout", status_code=204)
    async def logout(request: Request):
        """End the current session. Nothing happens if it already had, so signing out twice is not an error."""
        context.sessions.revoke(_bearer_token(request))

    @router.get("/me")
    async def me(admin: Signedin):
        return {"name": admin}


def _admin_routes(router: APIRouter, context: AdminContext, require_admin: Callable) -> None:
    """Administrators managing themselves and each other, once at least one of them is signed in."""
    Signedin = Annotated[str, Depends(require_admin)]

    def _save() -> None:
        save_admins(context.state_dir, context.admins)

    @router.get("/admins")
    async def list_admins(admin: Signedin):
        return [_account_dict(account, signed_in_as=admin) for account in context.admins.list_admins()]

    @router.post("/admins")
    async def add_admin(admin: Signedin, body: JsonBody):
        name, password = body.get("name"), body.get("password")
        if not (isinstance(name, str) and isinstance(password, str)):
            raise HTTPException(400, "a name and a password are needed")
        try:
            account = await asyncio.to_thread(context.admins.add, name, password, added=utc_now())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        _save()
        return _account_dict(account, signed_in_as=admin)

    @router.delete("/admins/{name}", status_code=204)
    async def remove_admin(name: str, admin: Signedin):
        try:
            context.admins.remove(name)
        except KeyError:
            raise HTTPException(404, f"{name!r} is not an administrator") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        context.sessions.revoke_all_of(name)
        _save()

    @router.post("/admins/{name}/password", status_code=204)
    async def change_password(name: str, admin: Signedin, body: JsonBody):
        password = body.get("password")
        if not isinstance(password, str):
            raise HTTPException(400, "a password is needed")
        try:
            await asyncio.to_thread(context.admins.change_password, name, password)
        except KeyError:
            raise HTTPException(404, f"{name!r} is not an administrator") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        _save()


def _settings_routes(
    router: APIRouter,
    suite: Suite,
    set_access_secret: Callable[[str | None], None],
    context: AdminContext,
    require_admin: Callable,
) -> None:
    """The settings themselves: the document cap, the access secret, the AI model, the LaTeX installation."""
    Signedin = Annotated[str, Depends(require_admin)]

    def _dict() -> dict:
        diagnosis = _diagnose_typeset(context.settings.typeset)
        return {**context.settings.to_public_dict(), "typeset_diagnosis": diagnosis}

    def _save() -> None:
        save_settings(context.state_dir, context.settings)

    @router.get("/settings")
    async def get_settings(admin: Signedin):
        return _dict()

    @router.put("/settings/max-documents")
    async def set_max_documents(admin: Signedin, body: JsonBody):
        value = body.get("max_documents")
        if not (isinstance(value, int) and not isinstance(value, bool) and value >= 1):
            raise HTTPException(400, "max_documents must be a whole number of at least 1")
        suite.max_documents = value
        context.settings.max_documents = value
        context.settings.note_changed("max_documents", admin)
        _save()
        return _dict()

    @router.get("/settings/access-secret")
    async def reveal_access_secret(admin: Signedin):
        """The access secret in the clear, for the settings page's "Reveal" button."""
        return {"access_secret": context.settings.access_secret}

    def _change_secret(value: str | None, admin: str) -> dict:
        try:
            set_access_secret(value)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        context.settings.access_secret = value
        context.settings.note_changed("access_secret", admin)
        _save()
        return _dict()

    @router.put("/settings/access-secret")
    async def put_access_secret(admin: Signedin, body: JsonBody):
        value = body.get("access_secret")
        if not (value is None or isinstance(value, str)):
            raise HTTPException(400, "access_secret must be a string or null")
        return _change_secret(value, admin)

    @router.post("/settings/access-secret/rotate")
    async def rotate_access_secret(admin: Signedin):
        """Replace the access secret with a freshly made one and reveal it once; rotating it never signs anyone
        out (it is not how administrators sign in — see ``admin.py``)."""
        value = secrets.token_urlsafe(24)
        return {"access_secret": value, **_change_secret(value, admin)}

    @router.put("/settings/ai")
    async def set_ai(admin: Signedin, body: JsonBody):
        settings = AiSettings(
            model_dir=body.get("model_dir"),
            device=body.get("device", context.settings.ai.device),
            max_tokens=body.get("max_tokens", context.settings.ai.max_tokens),
            timeout=body.get("timeout", context.settings.ai.timeout),
        )
        try:
            await context.ai.apply(suite, settings)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        context.settings.ai = settings
        context.settings.note_changed("ai", admin)
        _save()
        return _dict()

    @router.put("/settings/typeset")
    async def set_typeset(admin: Signedin, body: JsonBody):
        context.settings.typeset = TypesetSettings(xelatex=body.get("xelatex"), pdftocairo=body.get("pdftocairo"))
        context.settings.note_changed("typeset", admin)
        _save()
        return _dict()


def admin_router(suite: Suite, set_access_secret: Callable[[str | None], None], context: AdminContext) -> APIRouter:
    """The ``/api/admin`` routes, closed over ``suite`` (the server's apps), ``context`` (one per server) and
    ``set_access_secret`` (``Gateway.set_secret``, passed in rather than imported: see the module docstring)."""
    router = APIRouter(prefix="/api/admin")

    def require_admin(request: Request) -> str:
        admin = context.sessions.resolve(_bearer_token(request))
        if admin is None:
            raise HTTPException(401, "sign in as an administrator first", headers={"WWW-Authenticate": "Bearer"})
        return admin

    _identity_routes(router, context, require_admin)
    _admin_routes(router, context, require_admin)
    _settings_routes(router, suite, set_access_secret, context, require_admin)
    if context.fonts is not None:
        font_admin_routes(router, context.fonts, require_admin, lambda: context.settings.access_secret is not None)
    return router
