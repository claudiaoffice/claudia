"""The font report (E1.9, D1306): what a document asks for that this server does not have.

Said when a document is opened, for the banner. It never blocks anything (a document opens and is edited with the fonts it
lacks shown in their stand-ins), and it only *says*: getting a font is the administrator's, through Server settings ▸ Fonts,
which refuses everybody else whatever a page sent (``admin_fonts``, the rule of D251). What the report adds to the
catalogue's own answer is the one list a document needs: its fonts, each with what it will be shown in.
"""

from __future__ import annotations

from .protocol import Context, MethodTable


def add_font_report_method(table: MethodTable) -> None:
    """Add ``font_report`` to an app's method table."""

    @table.method("font_report")
    def font_report(ctx: Context) -> dict:
        """The fonts this document asks for that the server does not have: `{checked, missing}`. `missing` lists each as
        `{family, stand_in, closeness}`: `stand_in` is the family it will be shown in (`null` when there is none and the
        generic family of the style is used), `closeness` is `same-widths` when the stand-in takes the room of the
        font and `other` when nothing does. `checked` is false for a server that cannot say what it has (nothing is
        reported then). A read for anybody; it never blocks opening, and changes nothing."""
        catalogue = ctx.font_catalogue()
        if catalogue is None:
            return {"checked": False, "missing": []}
        missing = []
        for need in ctx.document.model.requirements().fonts:
            found = catalogue.resolve(need.family)
            if found.provided == need.family:
                continue
            missing.append({"family": need.family, "stand_in": found.provided, "closeness": found.closeness})
        return {"checked": True, "missing": missing}
