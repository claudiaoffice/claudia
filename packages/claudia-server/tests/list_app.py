"""The test app (``ListModel``, a list of numbers) plugged into the server the way a real app is: its own method table,
the core's plus named methods that build its changes (D2010).

The server's tests write through these methods, the seam every client uses (a named method, dispatch, a handler that
builds the change, ``Document.execute``), and never send a change in its stored form: no method takes one.
"""

from collections.abc import Callable

from claudia_core import Command, Revision
from claudia_core.testing import Insert, Remove
from claudia_server.protocol import Context, MethodTable, core_methods
from claudia_server.wire import done


def list_methods_for(
    insert: Callable[[int, int], Command] = Insert, remove: Callable[[int], Command] = Remove
) -> MethodTable:
    """The core table plus ``insert`` and ``remove``, building the given kinds of change (a test model with commands of
    its own, such as the redaction tests' naive list, passes its own)."""
    table = core_methods.extended()

    @table.method("insert", "index:int value:int base:revision?", write=True)
    def _insert(ctx: Context, *, index: int, value: int, base: Revision | None) -> dict:
        """Put `value` in front of the number at `index` (at the end for the length of the list)."""
        return done(ctx, insert(index, value), base)

    @table.method("remove", "index:int base:revision?", write=True)
    def _remove(ctx: Context, *, index: int, base: Revision | None) -> dict:
        """Take out the number at `index`."""
        return done(ctx, remove(index), base)

    return table


list_methods = list_methods_for()
