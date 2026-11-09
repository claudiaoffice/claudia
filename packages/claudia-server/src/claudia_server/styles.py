"""The style and palette methods every app shares (E1.10, D73, D75, D200).

A style book and a palette are :mod:`claudia_core`'s, not any one app's, so the methods that read and change them
belong here rather than three times over. :func:`add_style_methods` puts them in an app's table.

What stays with the app is the part that names the app's own things: composes' ``set_style`` and ``deviate_style``
take paragraph ids, and the equivalent for a slide or a sheet takes object ids, so each app registers its own.

``guard`` is how an app keeps a rule of its own. composes passes ``_people_only``: in a text the assistant suggests
and does not write (D63, SEC-10), and a style change is writing. The others pass nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from claudia_core import (
    BUILTIN_ROLES,
    Batch,
    ChangeStyle,
    ColourRole,
    Command,
    CreateStyle,
    Palette,
    RenameStyle,
    ReplacePalette,
    SetObjectStyle,
    SetRole,
    StyleBook,
    StyleDef,
    format_css,
    parse_css,
    validate_css,
)

from .protocol import Context, MethodTable, RequestError

#: A palette may not be replaced with more roles than the kernel would take anyway.
MAX_SENT_ROLES = 64
#: How many objects one deviation may restyle at once (composes has the same bound for paragraphs).
MAX_STYLED_OBJECTS = 200


def _rev(ctx: Context) -> str | None:
    revision = ctx.document.revision
    return None if revision is None else revision.to_data()


def _book(ctx: Context) -> StyleBook:
    book = getattr(ctx.document.model, "styles", None)
    if not isinstance(book, StyleBook):
        raise RequestError("bad_request", "this document has no styles")
    return book


def _palette(ctx: Context) -> Palette:
    palette = getattr(ctx.document.model, "palette", None)
    if not isinstance(palette, Palette):
        raise RequestError("bad_request", "this document has no palette")
    return palette


def own_css(properties: dict | None, text: str | None) -> dict[str, str] | None:
    """The CSS a request gave, as a dictionary: from ``set`` or from the text of a style; ``None`` for neither.

    Public because an app's own ``deviate_style`` takes its CSS exactly the same way.
    """
    if properties is not None and text is not None:
        raise RequestError("bad_request", "give the CSS as set properties or as text, not both")
    if text is None:
        return properties
    css, problems = parse_css(text)
    if problems:
        raise RequestError("command_error", "; ".join(p.message for p in problems))
    return css


def _roles_from(items: Iterable[object]) -> tuple[ColourRole, ...]:
    """The roles a request gave, each as ``{id, name, purpose, colour}``."""
    roles = []
    for item in items:
        if not isinstance(item, dict):
            raise RequestError("bad_request", "every role is an object with id, name, purpose and colour")
        try:
            roles.append(ColourRole(item["id"], item["name"], item["purpose"], item["colour"]))
        except KeyError as exc:
            raise RequestError("bad_request", f"a role is missing {exc.args[0]!r}") from None
        if not all(isinstance(value, str) for value in (roles[-1].id, roles[-1].name, roles[-1].colour)):
            raise RequestError("bad_request", "a role's id, name and colour are text")
    if len(roles) > MAX_SENT_ROLES:
        raise RequestError("bad_request", f"a palette holds at most {MAX_SENT_ROLES} colour roles")
    return tuple(roles)


def _only_what_differs(given: dict, inherited: dict[str, str]) -> dict[str, str]:
    """The CSS a deviation really needs: what the person asked for, minus whatever the parent already says.

    A new style that differs from its parent in nothing is not a style, it is a duplicate, so the caller refuses it.
    """
    wanted = validate_css(given)
    return {name: value for name, value in wanted.items() if inherited.get(name) != value}


def _changed(ctx: Context, command, base) -> dict:
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


def _add_palette_methods(table: MethodTable, allowed: Callable[[Context], None]) -> None:
    """The palette's own methods (D200). Split out of :func:`add_style_methods` only because the two
    together had grown past the statement limit — they belong side by side."""

    @table.method("palette")
    def _palette_method(ctx):
        """The document's colour roles as `{roles, readings}` (D200).

        A role is `{id, name, purpose, colour}`: `id` is what a style names as `@id` (or `@id/55` for that role at
        55% opacity), `name` and `purpose` are what to call it and what it means, and `colour` is `#rrggbb`.

        `builtin` is the palette a document starts with, so a client can offer "the colours it started with"
        without keeping a copy of its own that could drift from this one.

        A reading is `{foreground, background, ratio, floor, ok, words}`: how one role reads against another, the
        contrast it has to clear (4.5 for words, 3 for a border or a rule), and whether it does. `words` says
        which of the two it is. Say what a failing reading *means* — never show the ratio to a reader; a figure
        tells them nothing about whether they can read the page (D202)."""
        palette = _palette(ctx)
        return {
            "roles": palette.views(),
            "readings": [reading.to_data() for reading in palette.readings()],
            "builtin": [role.to_data() for role in BUILTIN_ROLES],
        }

    @table.method("set_role", "role:str colour:str base:revision?", write=True)
    def _set_role(ctx, *, role, colour, base):
        """Give one colour role another colour, as `#rrggbb`. Everything in the document that meant that role
        changes with it, in every style and every object at once.

        Nothing is refused for contrast: a person may pick any colour, and `palette` then reports what it costs
        (D202). `command_error` if there is no such role or the colour is not hexadecimal."""
        allowed(ctx)
        try:
            return _changed(ctx, SetRole(role, colour), base)
        except ValueError as exc:
            raise RequestError("command_error", str(exc)) from None

    @table.method("replace_palette", "roles:list base:revision?", write=True)
    def _replace_palette(ctx, *, roles, base):
        """Put a whole palette in place of the one the document has — each role `{id, name, purpose, colour}`.

        `command_error` if a style of this document names a role the new palette does not have: dropping it would
        change how the document looks without saying so, which is the one thing a palette exists to prevent."""
        allowed(ctx)
        try:
            return _changed(ctx, ReplacePalette(_roles_from(roles)), base)
        except ValueError as exc:
            raise RequestError("command_error", str(exc)) from None


def _add_object_style_methods(table: MethodTable, allowed: Callable[[Context], None]) -> None:
    """The two methods that style an *object* rather than a paragraph: pointing one at a style, and deviating
    from that style for the objects a person has selected (D75, D178, D203). Split out of
    :func:`add_style_methods` only to keep each under the statement limit."""

    @table.method("set_object_style", "id:str style:str base:revision?", write=True)
    def _set_object_style(ctx, *, id, style, base):
        """Put an object under another style of its own: what its box looks like — `fill`, `stroke` and
        `stroke-width` (D178).

        Not what its words look like: those follow the paragraph's own style, which `set_paragraph_style` points
        elsewhere. An object has the two, and they mean different things (D181). `command_error` if there is no
        such object or no such style."""
        allowed(ctx)
        try:
            return _changed(ctx, SetObjectStyle(id, style), base)
        except (KeyError, ValueError) as exc:
            raise RequestError("command_error", str(exc)) from None

    @table.method("deviate_object_style", "parent:str objects:list set:dict? text:text? base:revision?", write=True)
    def _deviate_object_style(ctx, *, parent, objects, set, text, base):
        """Make a new style from `parent` that differs in the CSS given (`set` properties, or `text`) and give it to
        the objects `objects`, in one step.

        This is "change this shape only": a change a person makes to one object does not quietly reach every other
        object that shares its style. The new style gets a provisional name such as “Plain shape (changed)” and is
        marked `to_name` until somebody names it (D75) — styles first, deviate second.

        Returns `{style, name, revision}`. `command_error` if nothing differs from the parent, if there is no such
        style, or if one of the objects is not there."""
        allowed(ctx)
        model = ctx.document.model
        if len(objects) > MAX_STYLED_OBJECTS or not all(isinstance(one, str) for one in objects):
            raise RequestError("bad_request", f"objects must be a list of at most {MAX_STYLED_OBJECTS} object ids")
        book = _book(ctx)
        try:
            inherited = book.computed(parent)
            for one in objects:
                model.get_object(one)  # KeyError -> command_error: the object has to be there
        except KeyError as exc:
            raise RequestError("command_error", exc.args[0]) from None
        own = _only_what_differs(own_css(set, text) or {}, inherited)
        if not own:
            raise RequestError("command_error", f"the new style would look just like “{book.get(parent).name}”")
        name = book.provisional_name(parent)
        made = StyleDef(book.unique_id(name), name, "", parent, own, to_name=True)
        steps: list[Command] = [CreateStyle(made), *(SetObjectStyle(one, made.id) for one in objects)]
        applied = ctx.document.execute(Batch(tuple(steps), "Deviate style"), author=ctx.user, base=base)
        return {"style": made.id, "name": name, "revision": applied.revision.to_data()}


def add_style_methods(table: MethodTable, *, guard: Callable[[Context], None] | None = None) -> None:
    """Register the shared style and palette methods in ``table``.

    ``guard`` runs before every one that writes; see the module docstring.
    """
    allowed = guard if guard is not None else (lambda ctx: None)
    _add_palette_methods(table, allowed)
    _add_object_style_methods(table, allowed)

    @table.method("styles")
    def _styles(ctx):
        """The document's styles, each as `{id, name, purpose, based_on, css, computed, resolved, to_name}`.

        `css` is what the style sets itself, `computed` the CSS it really has once its parents (`based_on`) are
        taken in (D73), and `resolved` the same again with every palette role (`@accent`) replaced by the literal
        colour the palette gives it — that last one is what a client draws with, so the CSS it puts on a page is
        always literal. `to_name` is true for a style that was made by deviating and still has the provisional
        name it was given (E9.7). A shape's background and border are `fill`/`stroke`/`stroke-width` (D178)."""
        return _book(ctx).views(_palette_colours(ctx))

    @table.method("change_style", "style:str set:dict? unset:list? text:text? base:revision?", write=True)
    def _change_style(ctx, *, style, set, unset, text, base):
        """Change a style for everything that has it (and for the styles based on it, where they do not set the
        property themselves). Either `set` properties (`{"color": "@accent"}`) and `unset` property names, or
        `text`, the complete CSS text of the style, which replaces what it sets.

        A colour may be a palette role (`@accent`, `@accent/55`) as well as a literal (D200). `command_error`
        names every property that is not allowed. A change that changes nothing is not an edit (`revision` is
        then null)."""
        allowed(ctx)
        known = _book(ctx)
        try:
            own = known.get(style).css
        except KeyError as exc:
            raise RequestError("command_error", exc.args[0]) from None
        wanted = own_css(set, text)
        if text is not None:
            assert wanted is not None
            change = {name: value for name, value in wanted.items() if own.get(name) != value}
            removed = tuple(name for name in own if name not in wanted)
        else:
            if unset is not None and not all(isinstance(name, str) for name in unset):
                raise RequestError("bad_request", "unset must be a list of property names")
            removed = tuple(name for name in dict.fromkeys(unset or ()) if name in own)
            change = validate_css(wanted or {})
            change = {name: value for name, value in change.items() if own.get(name) != value}
        if not change and not removed:
            return {"revision": _rev(ctx)}
        return _changed(ctx, ChangeStyle(style, change, removed), base)

    @table.method("rename_style", "style:str name:str base:revision?", write=True)
    def _rename_style(ctx, *, style, name, base):
        """Give a style the name its maker chose. That ends the invitation to name it. `command_error` if another
        style has that name (in any letters) or the name is empty, long, or more than one line."""
        allowed(ctx)
        return _changed(ctx, RenameStyle(style, name, False), base)

    @table.method("check_css", "text:text")
    def _check_css(ctx, *, text):
        """Check the CSS text of a style without changing anything (so viewers may ask, and a client can check
        while somebody types): `{css, text, problems}` with the valid declarations, the same in the fixed order a
        style is written in, and a problem `{line, property, message}` for each line that is not allowed."""
        css, problems = parse_css(text)
        return {"css": css, "text": format_css(css), "problems": [p.to_data() for p in problems]}


def _palette_colours(ctx: Context) -> dict[str, str] | None:
    """The document's role colours, or ``None`` for a document that has no palette at all."""
    palette = getattr(ctx.document.model, "palette", None)
    return palette.colours() if isinstance(palette, Palette) else None
