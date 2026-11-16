"""The page's files on this computer (D501, D502): the Open and Save dialogs, reading the chosen file and writing the
saved one, and handing a PDF to the computer's viewer to print it. No GTK in here (``window.GtkDialogs`` shows the
dialogs), so it is tested with fake dialogs and a temporary folder; the twin of ``clients/neutralino/src/files.ts``.

The page cannot do this itself: a file input cannot be opened from a menu item (which is no click in the page), and a
download goes into the Downloads folder without a word about it. A file travels in pieces (``file_chunk``, 36 KiB of
bytes each, as base64), because a message of the shell contract has at most 64 KiB.
"""

from __future__ import annotations

import base64
import binascii
import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from . import contract
from .i18n import translate as _

__all__ = ["Dialogs", "Files", "Reply"]

log = logging.getLogger(__name__)

Chosen = Callable[[Path | None], None]
"""Called with the chosen path, or ``None`` when the person cancelled."""
Failed = Callable[[str], None]
"""Called with why the dialog could not be shown."""


class Dialogs(Protocol):
    """The computer's own dialogs and viewer. They answer later, through the callbacks (GTK's dialogs are async)."""

    def open(self, title: str, extensions: list[str], folder: Path | None, chosen: Chosen, failed: Failed) -> None: ...

    def save(
        self, title: str, name: str, extensions: list[str], folder: Path | None, chosen: Chosen, failed: Failed
    ) -> None: ...

    def show(self, path: Path, done: Callable[[], None], failed: Failed) -> None:
        """Open ``path`` with the computer's application for its kind (the PDF viewer, which prints)."""


class Reply(Protocol):
    """How the answers go to the page (the bridge's ``send_file_*``)."""

    def send_file_result(self, request: str, outcome: str, **details: object) -> bool: ...
    def send_file_offer(self, request: str, name: str, size: int) -> bool: ...
    def send_file_chunk(self, request: str, index: int, data: str) -> bool: ...
    def send_file_done(self, request: str, chunks: int) -> bool: ...


@dataclass
class _Incoming:
    name: str
    size: int
    purpose: str
    pieces: list[bytes] = field(default_factory=list)
    received: int = 0
    broken: str | None = None


def _plain_name(name: str) -> str:
    """A file name and nothing else: no folder, nothing that would climb out of the print folder."""
    base = Path(name.replace("\\", "/")).name
    return base if base not in ("", ".", "..") else "claudia-file"


def _extension_of(name: str) -> list[str]:
    suffix = Path(name).suffix[1:].lower()
    return [suffix] if suffix.isalnum() and suffix.isascii() and 0 < len(suffix) <= 16 else []


class Files:
    """The shell's file desk (``bridge.FileDesk``)."""

    def __init__(
        self,
        dialogs: Dialogs,
        reply: Reply,
        *,
        documents: Path,
        print_folder: Path | None = None,
    ) -> None:
        self._dialogs = dialogs
        self._reply = reply
        self._documents = documents
        self._print_folder = print_folder or Path(tempfile.gettempdir()) / "claudia-print"
        self._incoming: dict[str, _Incoming] = {}
        self._last_folder: Path | None = None
        """The folder of the last file opened or saved: the next dialog starts there."""
        self._offers = 0

    def _read(self, request: str, path: Path) -> bytes | None:
        """The bytes of ``path``, or ``None`` after telling the page why not."""
        try:
            size = path.stat().st_size
            if size > contract.MAX_FILE_BYTES:
                self._fail(
                    request,
                    _("{name} is larger than {mb} MB.").format(
                        name=path.name, mb=contract.MAX_FILE_BYTES // 1024 // 1024
                    ),
                )
                return None
            return path.read_bytes()
        except OSError as problem:
            self._fail(request, _("{name} could not be read: {reason}").format(name=path.name, reason=problem))
            return None

    def _send_pieces(self, request: str, data: bytes) -> None:
        step = contract.FILE_CHUNK_BYTES
        pieces = range(0, len(data), step)
        for index, at in enumerate(pieces):
            self._reply.send_file_chunk(request, index, base64.b64encode(data[at : at + step]).decode("ascii"))
        self._reply.send_file_done(request, len(pieces))

    def offer(self, path: Path) -> bool:
        """D505: the person dropped ``path`` on the window; hand it to the page as if it had been dropped there.
        ``False`` when it is not a file that can be read (nothing is sent then)."""
        try:
            if not path.is_file() or path.stat().st_size > contract.MAX_FILE_BYTES:
                return False
            data = path.read_bytes()
        except OSError as problem:
            log.warning("a dropped file could not be read: %s", problem)
            return False
        self._offers += 1
        request = f"drop-{self._offers}"
        self._last_folder = path.parent
        self._reply.send_file_offer(request, path.name, len(data))
        self._send_pieces(request, data)
        return True

    def _fail(self, request: str, message: str) -> None:
        log.warning("file %s: %s", request, message)
        self._reply.send_file_result(request, "failed", message=message)

    # ------------------------------------------------------------------------------------------------- choosing

    def pick(self, request: str, accept: list[str], title: str | None) -> None:
        """Show the Open dialog; send the chosen file to the page in pieces."""

        def chosen(path: Path | None) -> None:
            if path is None:
                self._reply.send_file_result(request, "cancelled")
                return
            data = self._read(request, path)
            if data is None:
                return
            self._last_folder = path.parent
            self._reply.send_file_result(request, "picked", name=path.name, size=len(data))
            self._send_pieces(request, data)

        self._dialogs.open(
            title or _("Open a File"),
            accept,
            self._last_folder,
            chosen,
            lambda why: self._fail(request, _("The Open dialog could not be shown: {reason}").format(reason=why)),
        )

    # --------------------------------------------------------------------------------------------------- saving

    def begin(self, request: str, name: str, size: int, purpose: str) -> None:
        self._incoming[request] = _Incoming(_plain_name(name), size, purpose)

    def chunk(self, request: str, index: int, data: str) -> None:
        file = self._incoming.get(request)
        if file is None or file.broken is not None:
            return
        if index != len(file.pieces):
            file.broken = "a piece of the file went missing on the way"
            return
        try:
            piece = base64.b64decode(data, validate=True)
        except binascii.Error:
            file.broken = "a piece of the file arrived damaged"
            return
        file.received += len(piece)
        if file.received > file.size:
            file.broken = "more of the file arrived than was announced"
            return
        file.pieces.append(piece)

    def done(self, request: str, chunks: int) -> None:
        file = self._incoming.pop(request, None)
        if file is None:
            return
        if file.broken is None and (chunks != len(file.pieces) or file.received != file.size):
            file.broken = "the file did not arrive whole"
        if file.broken is not None:
            self._fail(request, _("The file could not be saved: {reason}").format(reason=file.broken))
            return
        data = b"".join(file.pieces)
        if file.purpose == "print":
            self._print(request, file.name, data)
            return

        def chosen(path: Path | None) -> None:
            if path is None:
                self._reply.send_file_result(request, "cancelled")
                return
            try:
                path.write_bytes(data)
            except OSError as problem:
                self._fail(request, _("{path} could not be written: {reason}").format(path=path, reason=problem))
                return
            self._last_folder = path.parent
            log.info("file %s: saved %d bytes as %s", request, len(data), path)
            self._reply.send_file_result(request, "saved", path=str(path))

        self._dialogs.save(
            _("Save"),
            file.name,
            _extension_of(file.name),
            self._last_folder or self._documents,
            chosen,
            lambda why: self._fail(request, _("The Save dialog could not be shown: {reason}").format(reason=why)),
        )

    def _print(self, request: str, name: str, data: bytes) -> None:
        """D502: the PDF goes into a folder of its own and the computer's viewer opens it; its Print prints it."""
        path = self._print_folder / name
        try:
            self._print_folder.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as problem:
            self._fail(request, _("The pages could not be opened to print: {reason}").format(reason=problem))
            return

        def opened() -> None:
            self._reply.send_file_result(request, "opened", path=str(path))

        self._dialogs.show(
            path,
            opened,
            lambda why: self._fail(request, _("The pages could not be opened to print: {reason}").format(reason=why)),
        )
