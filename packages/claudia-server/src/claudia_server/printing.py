"""What every app that prints answers on the wire (D917): the language of the document.

The language is the kernel's (:class:`~claudia_core.SetLanguage`), the same in composes and creates, and so are these
two methods; each app adds how its own pages are set up (composes: ``page``/``set_page``, D904; creates:
``print_setup``/``set_print_setup``, D917).
"""

from __future__ import annotations

from claudia_core import LanguageError, SetLanguage

from .i18n import msg
from .protocol import Context, MethodTable, RequestError


def people_only(ctx: Context) -> None:
    """The assistant suggests; it does not change how a document is set up (D63)."""
    if ctx.account.system:
        raise RequestError("forbidden", msg("the assistant can only make suggestions; people set the document up"))


def add_language_methods(table: MethodTable) -> None:
    """``language`` and ``set_language``, for a table whose documents have a ``language`` (D915, D917)."""

    @table.method("language")
    def _language(ctx):
        """The language the document is written in, as `{language}`: a BCP 47 tag such as `de` or `en-GB`, or
        `null`."""
        return {"language": ctx.document.model.language}

    @table.method("set_language", "language:str? base:revision?", write=True)
    def _set_language(ctx, *, language, base):
        """Say which language the document is written in (`null` or `""`: not known). One step for everybody, in
        the history; the pages are hyphenated by it. `command_error` for a value that is not a language tag."""
        people_only(ctx)
        try:
            command = SetLanguage(language or None)
        except LanguageError as exc:
            raise RequestError("command_error", str(exc)) from None
        applied = ctx.document.execute(command, author=ctx.user, base=base)
        return {"revision": applied.revision.to_data()}
