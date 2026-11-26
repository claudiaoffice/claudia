"""The test app (``ListModel``, a list of numbers) plugged into the server the way a real app is: its own method table,
the core's plus named methods that build its changes (D2010).

The server's tests write through these methods, the seam every client uses (a named method, dispatch, a handler that
builds the change, ``Document.execute``), and never send a change in its stored form: no method takes one.
"""

from claudia_core.testing import Insert, Remove
from claudia_server.protocol import MethodTable, core_methods


def list_methods_for(insert=Insert, remove=Remove) -> MethodTable:
    """The core table plus ``insert`` and ``remove``, building the given kinds of change (a test model with commands of
    its own, such as the redaction tests' naive list, passes its own)."""
    table = core_methods.extended()

    def done(applied) -> dict:
        return {"revision": applied.revision.to_data()}

    @table.method("insert", "index:int value:int base:revision?", write=True)
    def _insert(ctx, *, index, value, base):
        """Put `value` in front of the number at `index` (at the end for the length of the list)."""
        return done(ctx.document.execute(insert(index, value), author=ctx.user, base=base))

    @table.method("remove", "index:int base:revision?", write=True)
    def _remove(ctx, *, index, base):
        """Take out the number at `index`."""
        return done(ctx.document.execute(remove(index), author=ctx.user, base=base))

    return table


list_methods = list_methods_for()
