"""``/api/admin/*``: the server settings pages, and nothing else (E3.1, D5x).

Everything here is about the *server* — who may configure it and what it is configured to do — never about a
document; a document's own protocol (``app.py``) does not call into this module and this module does not call into
it. Every route but ``status``, ``setup``, ``setup-code`` and ``login`` needs a current administrator session
(``Authorization: Bearer <token>``, issued by ``login`` or ``setup``); :func:`admin_router` is the one way in.

``AdminContext`` is everything the routes need that is not already on the ``Suite``: the administrators themselves,
their sessions, the server's settings, where to persist both, whether this server is exposed beyond this computer
(decided once, at bind time, from the already-existing ``is_loopback`` signal: see ``cli.py``), and ``AiRuntime`` for
the one setting that is more than a value to remember — changing the AI model restarts the model itself (see
:meth:`AiRuntime.apply`). The one thing it does *not* carry is a way to change the access secret: that belongs to the
``Gateway`` that ``create_app`` builds, so ``admin_router`` takes it as a plain function instead (there is no other
reason for this module to know what a ``Gateway`` is)."""

import asyncio
import logging
import math
import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from claudia_ai import ClaudeModel, FailureReason, ModelError, ModelRunner, OpenVinoModel, ProviderError
from claudia_ai.claude import DEFAULT_BASE_URL
from claudia_core import DocumentModel
from claudia_core.clock import utc_now
from claudia_typeset.programs import EngineUnavailable, resolve_program

from .admin import AdminAccount, AdminDirectory, needs_administrator
from .admin_fonts import font_admin_routes
from .admin_sessions import AdminSessions
from .admin_start import ResetNote, dismiss_reset_note
from .admin_templates import template_admin_routes
from .ai_desk import ProviderDesk
from .apps import has_lens, routed_assistant_for
from .assistant import Assistant
from .fonts import FontService
from .kdf_policy import KdfPolicy, check_target
from .login_throttle import LoginThrottle
from .server_settings import (
    CLAUDE,
    LOCAL,
    PROVIDERS,
    STAND_IN,
    AiSettings,
    Changed,
    ClaudeSettings,
    ServerSettings,
    TypesetSettings,
    save_admins,
    save_settings,
)
from .setup_code import SetupCode, remove_code
from .suite import Suite
from .template_library import TemplateLibrary

log = logging.getLogger("claudia_server")
JsonBody = Annotated[dict, Body()]


def assistants_for(
    models: Iterable[type[DocumentModel]], desk: ProviderDesk
) -> dict[str, Callable[[], Assistant] | None]:
    """Who answers ``@ai`` in each app, by app: whoever ``desk`` says for each question (the scripted stand-in, the
    local model or Claude, E7.11). ``None`` for an app that has neither a stand-in nor a language-model lens."""
    return {model.app: routed_assistant_for(model, desk) for model in models}


def any_lens(models: Iterable[type[DocumentModel]]) -> bool:
    """Can a language model work in at least one of these apps?"""
    return any(has_lens(model) for model in models)


class AiRefused(ValueError):
    """Anthropic did not accept what the administrator applied; ``reason`` says why (it is on the page, E7.11)."""

    def __init__(self, reason: FailureReason, sentence: str):
        super().__init__(sentence)
        self.reason = reason


APPROVAL_SENTENCE = "Document content is sent to Anthropic when someone asks @ai."
TEST_QUESTION = [{"role": "user", "content": "Answer with the single word: ok."}]


@dataclass
class AiRuntime:
    """Where the admin API finds, and changes, the AI user's language model while the server runs.

    ``enabled`` is ``False`` for a server started with ``--no-assistant``: an operator's own decision that the
    settings pages must not be able to undo. ``models`` are the document models of the server's apps — the
    model-driven assistant is described to the language model in their terms (``apps.model_assistant_for``); one
    model serves all of them (D432)."""

    models: tuple[type[DocumentModel], ...]
    enabled: bool
    desk: ProviderDesk = field(default_factory=ProviderDesk)
    """The providers and whether Claude was approved, as the settings page set them (``ProviderDesk``)."""
    anthropic_key: str | None = None
    """A provider key the operator gave (``ANTHROPIC_API_KEY``, ``--anthropic-key-file``): it wins over the saved one
    (D154), and the settings page cannot change or remove it."""
    anthropic_url: str | None = None
    """The address of Anthropic, for tests and a proxy. Never a field of a page, as it would send the key anywhere."""

    def key_in_use(self, settings: AiSettings) -> str | None:
        """The provider key that is used: the operator's, else the saved one."""
        return self.anthropic_key or settings.claude.key

    def claude_model(self, settings: AiSettings) -> ClaudeModel:
        """Claude, as ``settings`` describe it. ``ValueError`` if there is no key."""
        key = self.key_in_use(settings)
        if key is None:
            raise ValueError("Claude needs a provider key.")
        return ClaudeModel(
            key, settings.claude.model, base_url=self.anthropic_url or DEFAULT_BASE_URL, read_timeout=settings.timeout
        )

    async def _test_claude(self, settings: AiSettings) -> None:
        """Ask Claude one question, so that a wrong key or model is found where the administrator is looking."""
        model = self.claude_model(settings)
        try:
            await asyncio.to_thread(model.generate, TEST_QUESTION, max_new_tokens=8, stop=lambda: False)
        except ProviderError as error:
            sentence = error.reason.admin_sentence(
                model=settings.claude.model, seconds=settings.timeout, detail=error.detail
            )
            raise AiRefused(error.reason, sentence) from error

    @property
    def runner(self) -> ModelRunner | None:
        """The local model that is loaded, if any."""
        return self.desk.local

    def claude_runner(self, settings: AiSettings) -> ModelRunner:
        """Claude behind its own worker, as ``settings`` describe it. ``ValueError`` if there is no key."""
        return ModelRunner(
            self.claude_model(settings), max_new_tokens=settings.claude.max_tokens, timeout=settings.timeout
        )

    async def apply(self, suite: Suite, settings: AiSettings) -> None:
        """Make ``settings`` the AI user's configuration in every app of ``suite``, from now on: for every question
        asked after this, in documents opened before as well as after (each document's router asks the desk, E7.11).
        A question that is running on a model this replaces is stopped. Closes what it replaces.

        The local model is loaded whenever a model folder is set and the provider is not the stand-in: with Claude
        chosen it is what answers in documents whose owners did not allow Claude.

        ``ValueError`` if the AI is disabled for this server, the model cannot be loaded, Anthropic does not accept the
        key, or none of this server's apps has an assistant for the model."""
        if not self.enabled:
            raise ValueError("the AI assistant is disabled for this server (it was started with --no-assistant)")
        if settings.provider == CLAUDE:
            await self._test_claude(settings)
        local = None
        if settings.model_dir and settings.provider != STAND_IN:
            local = await self._load(settings.model_dir, settings, required=settings.provider == LOCAL)
        claude = self.claude_runner(settings) if settings.provider == CLAUDE else None
        replaced = self.desk.install(
            provider=settings.provider, local=local, claude=claude, approved=settings.claude.confirmed is not None
        )
        for app, factory in assistants_for(self.models, self.desk).items():
            module = suite.module(app)
            if module is not None:
                module.hub.assistant = factory
        for runner in replaced:
            await asyncio.to_thread(runner.close)

    async def _load(self, model_dir: str, settings: AiSettings, *, required: bool) -> ModelRunner | None:
        """The local model of ``model_dir``. With ``Claude`` as the provider a model that cannot be loaded is not a
        reason to refuse Claude: the stand-in answers where the model would have."""
        try:
            runner = await asyncio.to_thread(
                lambda: ModelRunner(
                    OpenVinoModel(model_dir, settings.device),
                    max_new_tokens=settings.max_tokens,
                    timeout=settings.timeout,
                )
            )
        except ModelError as exc:
            if not required:
                log.warning("the local model could not be loaded, the stand-in answers instead: %s", exc)
                return None
            raise ValueError(str(exc)) from exc
        if required and not any_lens(self.models):
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
    templates: TemplateLibrary | None = None
    """The server's templates, for Server settings ▸ Templates (``admin_templates``); ``None`` for a server without."""
    kdf: KdfPolicy | None = None
    """What password hashing costs for new documents, for Server settings ▸ Security (D1267); ``None`` for a server
    that keeps no documents of its own."""
    setup_code: SetupCode | None = None
    """The code that ``setup`` asks for while nobody is named (D1370, D1371); ``None`` once somebody is, and for a
    server that made none, which then lets nobody set up."""
    reset_note: ResetNote | None = None
    """When the administrators were last reset from the console, until one of them dismisses it (D1375)."""


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


ADMIN_LOGIN = (
    "\x00admin"  # the "document" of the administrators' sign-in in the login counters: no document is called so
)
ADMIN_SETUP = "\x00setup"  # the same for tries of the setup code (D1371); its "name" is always empty
WRONG_CODE = "that is not this server's setup code; look in the log of its last start (a restart makes a new code)"
TAKEN = "this server already has an administrator; sign in to add another"


def _too_many(seconds: float) -> JSONResponse:
    """429 with the wait in ``Retry-After`` and ``retry_after`` (D1266)."""
    whole = max(1, math.ceil(seconds))
    return JSONResponse(
        status_code=429,
        content={"detail": f"too many tries; try again in {whole} s", "retry_after": whole},
        headers={"Retry-After": str(whole)},
    )


def _identity_routes(
    router: APIRouter,
    context: AdminContext,
    require_admin: Callable,
    throttle: LoginThrottle | None,
    address_of: Callable[[Request], str],
) -> None:
    """``status``, ``setup``, ``login``, ``logout``, ``me``: becoming and being an administrator."""
    Signedin = Annotated[str, Depends(require_admin)]

    @router.get("/status")
    async def status():
        """Public: whether this server needs somebody to become its first administrator (``exposed`` and nobody
        is one yet), and whether ``setup`` asks for a setup code (``setup_code``: never the code itself, D1371). A
        settings page checks this before anything else, since it decides what to show.

        ``administrator`` is the earliest-added administrator's name, or ``null`` if there is none yet — a hint a
        client can turn into a friendly label ("<name>'s server") before anyone has signed in to this server in
        this browser; it carries no authority and nothing here requires a session."""
        needs = needs_administrator(context.exposed, len(context.admins))
        first = context.admins.list_admins()
        return {
            "needs_administrator": needs,
            "exposed": context.exposed,
            "administrator": first[0].name if first else None,
            "setup_code": not first and context.setup_code is not None,
        }

    def _check_code(request: Request, given: object) -> JSONResponse | None:
        """The refusal for a try of the setup code, or ``None`` if ``given`` is this run's code (D1371): 429 inside
        a wait, 409 once somebody is named, 403 for a wrong code (counted)."""
        address = address_of(request)
        if throttle is not None and (wait := throttle.check(address, ADMIN_SETUP, "")) > 0:
            return _too_many(wait)
        if len(context.admins) > 0:
            return JSONResponse(status_code=409, content={"detail": TAKEN})
        if context.setup_code is None or not context.setup_code.matches(given):
            if throttle is not None:
                throttle.failed(address, ADMIN_SETUP, "")
            return JSONResponse(status_code=403, content={"detail": WRONG_CODE})
        return None

    @router.post("/setup-code", status_code=204)
    async def check_setup_code(body: JsonBody, request: Request):
        """Is this the setup code? For a code that came with a link (D1372); a try like any other."""
        if (refused := _check_code(request, body.get("code"))) is not None:
            return refused
        return None

    @router.post("/setup")
    async def setup(body: JsonBody, request: Request):
        """Become this server's first administrator, with the setup code of this run (D1370). Refused once it has
        one — sign in and add another instead."""
        if (refused := _check_code(request, body.get("code"))) is not None:
            return refused
        name, password = body.get("name"), body.get("password")
        if not (isinstance(name, str) and isinstance(password, str)):
            raise HTTPException(400, "a name and a password are needed")
        try:
            account = await asyncio.to_thread(context.admins.add, name, password, added=utc_now())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        save_admins(context.state_dir, context.admins)
        context.setup_code = None
        remove_code(context.state_dir)
        if throttle is not None:
            throttle.succeeded(address_of(request))
        token = context.sessions.issue(account.name)
        return {"token": token, "admin": _account_dict(account, signed_in_as=account.name)}

    @router.post("/login")
    async def login(body: JsonBody, request: Request):
        """Sign in as an existing administrator. Failed sign-ins wait longer each time (D1266): inside a wait the
        answer is 429 with the seconds in ``Retry-After`` and ``retry_after``, before any hashing."""
        name, password = body.get("name"), body.get("password")
        address = address_of(request)
        if throttle is not None and (wait := throttle.check(address, ADMIN_LOGIN, name)) > 0:
            return _too_many(wait)
        account = await asyncio.to_thread(context.admins.verify, name, password)
        if account is None:
            if throttle is not None:
                throttle.failed(address, ADMIN_LOGIN, name)
            raise HTTPException(401, "wrong name or password")
        if throttle is not None:
            throttle.succeeded(address)
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

    @router.get("/reset-note")
    async def reset_note(admin: Signedin):
        """When the administrators were last reset from the console and who they were (D1375), or ``null``."""
        note = context.reset_note
        return None if note is None else note.to_data()

    @router.delete("/reset-note", status_code=204)
    async def dismiss_reset(admin: Signedin):
        """An administrator has read the note: nobody sees it again. Dismissing twice is no error."""
        context.reset_note = None
        dismiss_reset_note(context.state_dir)

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


def settings_view(context: AdminContext) -> dict:
    """What a settings page shows: the public settings, how the LaTeX programs were found, and what password hashing
    costs for new documents now (``None`` for a server with no sealed documents)."""
    kdf = context.kdf.describe() if context.kdf is not None else None
    diagnosis = _diagnose_typeset(context.settings.typeset)
    view = context.settings.to_public_dict()
    key = context.ai.key_in_use(context.settings.ai)
    view["ai"]["claude"] |= {
        "key_set": key is not None,
        "key_tail": key[-4:] if key else None,
        "key_from_operator": context.ai.anthropic_key is not None,
    }
    view["ai"] |= _ai_state(context)
    return {**view, "typeset_diagnosis": diagnosis, "kdf": kdf}


def _ai_state(context: AdminContext) -> dict:
    """What answers now and what went wrong with it last, in the words of the AI page (E7.11)."""
    desk, settings = context.ai.desk, context.settings.ai
    failure = desk.health.last
    last_error = None
    if failure is not None:
        sentence = failure.reason.admin_sentence(
            model=settings.claude.model, seconds=settings.timeout, detail=failure.detail
        )
        last_error = {
            "provider": failure.provider,
            "reason": failure.reason.value,
            "sentence": sentence,
            "when": failure.when,
        }
    return {"answering": desk.answering_now().to_data(), "last_error": last_error}


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
        return settings_view(context)

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
        try:
            settings = _ai_settings_asked(context, body, admin)
            await context.ai.apply(suite, settings)
        except AiRefused as exc:
            return JSONResponse({"detail": str(exc), "reason": exc.reason.value}, status_code=400)
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


def _ai_settings_asked(context: AdminContext, body: dict, admin: str) -> AiSettings:
    """The AI settings a ``PUT`` asks for, on top of those there are. ``ValueError`` for what cannot be."""
    before = context.settings.ai
    model_dir = body.get("model_dir", before.model_dir) if "provider" in body else body.get("model_dir")
    provider = body.get("provider") or (LOCAL if model_dir else STAND_IN)
    if provider not in PROVIDERS:
        raise ValueError(f"the provider must be one of: {', '.join(PROVIDERS)}")
    if provider == LOCAL and not model_dir:
        raise ValueError("the local model needs a model folder")
    asked = body.get("claude", {})
    key = None if asked.get("remove_key") else asked.get("key", before.claude.key)
    claude = ClaudeSettings(
        asked.get("model") or before.claude.model,
        key,
        before.claude.confirmed,
        max_tokens=asked.get("max_tokens", before.claude.max_tokens),
    )
    if not isinstance(claude.max_tokens, int) or isinstance(claude.max_tokens, bool) or claude.max_tokens < 1:
        raise ValueError("the answer length must be at least 1")
    if provider == CLAUDE:
        if context.ai.key_in_use(AiSettings(claude=claude)) is None:
            raise ValueError("Claude needs a provider key.")
        if before.provider != CLAUDE:
            if not asked.get("confirm"):
                raise ValueError(f"Confirm first: {APPROVAL_SENTENCE}")
            claude.confirmed = Changed(admin, utc_now())
    return AiSettings(
        provider=provider,
        model_dir=model_dir,
        device=body.get("device", before.device),
        max_tokens=body.get("max_tokens", before.max_tokens),
        timeout=body.get("timeout", before.timeout),
        claude=claude,
    )


def _security_routes(router: APIRouter, context: AdminContext, require_admin: Callable) -> None:
    """Server settings ▸ Security (D1267): how slow password hashing is for the documents made from now on."""
    Signedin = Annotated[str, Depends(require_admin)]

    @router.put("/settings/security")
    async def set_security(admin: Signedin, body: JsonBody):
        try:
            target = check_target(body.get("kdf_target_seconds"))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        context.settings.security.kdf_target_seconds = target
        context.settings.note_changed("security", admin)
        save_settings(context.state_dir, context.settings)
        if context.kdf is not None:
            context.kdf.retarget(target)
        return settings_view(context)


def admin_router(
    suite: Suite,
    set_access_secret: Callable[[str | None], None],
    context: AdminContext,
    *,
    throttle: LoginThrottle | None = None,
    address_of: Callable[[Request], str] = lambda request: request.client.host if request.client else "",
) -> APIRouter:
    """The ``/api/admin`` routes, closed over ``suite`` (the server's apps), ``context`` (one per server) and
    ``set_access_secret`` (``Gateway.set_secret``, passed in rather than imported: see the module docstring).

    With a ``throttle`` (the gateway's, so that an address has one count for both doors) failed sign-ins wait longer
    each time (D1266); ``address_of`` says who a request is, behind a proxy too (D1275)."""
    router = APIRouter(prefix="/api/admin")

    def require_admin(request: Request) -> str:
        admin = context.sessions.resolve(_bearer_token(request))
        if admin is None:
            raise HTTPException(401, "sign in as an administrator first", headers={"WWW-Authenticate": "Bearer"})
        return admin

    _identity_routes(router, context, require_admin, throttle, address_of)
    _admin_routes(router, context, require_admin)
    _settings_routes(router, suite, set_access_secret, context, require_admin)
    _security_routes(router, context, require_admin)
    if context.fonts is not None:
        font_admin_routes(router, context.fonts, require_admin, lambda: context.settings.access_secret is not None)
    if context.templates is not None:
        template_admin_routes(router, context.templates, require_admin)
    return router
