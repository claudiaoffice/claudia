"""What the command log says about a document's dates and people, for the metadata of an export (D411).

The model keeps no time: when a document was made, when it was last changed and when a suggestion was proposed are all
in the log, which stamps every entry with the server's time and the author's name. A converter does not read logs;
:func:`export_info` reads it for them and hands over what the converters take."""

from __future__ import annotations

from claudia_composes import ProposeSuggestion
from claudia_core import Batch, Command, CommandLog
from claudia_odf_io import DocumentInfo


def _proposals(command: Command) -> list[ProposeSuggestion]:
    if isinstance(command, ProposeSuggestion):
        return [command]
    if isinstance(command, Batch):
        return [found for inner in command.commands for found in _proposals(inner)]
    return []


def export_info(log: CommandLog, branch: str | None = None) -> tuple[DocumentInfo, dict[str, str]]:
    """The :class:`~claudia_odf_io.DocumentInfo` of the document the log makes on ``branch`` (the active line), and
    when each suggestion was proposed, as ``{suggestion id: time}``.

    The document was made, by whom, with its first change, and last changed, by whom, with its last. An empty log
    knows none of this. Entries that undo or redo something are not changes of their own, and a suggestion that was
    proposed is dated by the entry that proposed it, whatever happened to it since (the converters only write the open
    ones). The title is not in the log (it is the container's): the caller adds it with ``dataclasses.replace``."""
    path = log.path(log.head(branch if branch is not None else log.active))
    times = {
        proposal.id: entry.time
        for entry in path
        if entry.origin == "do" and not entry.redacted
        for proposal in _proposals(entry.command)
    }
    if not path:
        return DocumentInfo(), times
    first, last = path[0], path[-1]
    return DocumentInfo(None, first.time, first.author, last.time, last.author), times
