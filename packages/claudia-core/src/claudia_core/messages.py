"""The three message classes (E1.6, D32, D34, D37).

======================  ==========================  ===============================  =====================
class                   examples                    where it lives                   key domain (D34)
======================  ==========================  ===============================  =====================
durable command         SetCells, checkpoint        the command log                  content / history
chat record             "@ana please check B4"      the chat store, never the log    chat
ephemeral message       presence, what-if preview,  nowhere: delivered, then gone     none
                        typing indicator
======================  ==========================  ===============================  =====================

The separation is structural: ``Document.publish`` (ephemeral) has no path to a store, ``Document.post_chat``
writes only to the chat store, and ``Document.execute`` writes only to the log.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from .revision import Revision

CHAT_MAX = 2_000  # characters in one chat message
EVERYBODY = ""  # the recipient of a message that is for everybody


@dataclass(frozen=True)
class ChatRecord:
    number: int  # position in the chat, from 1
    author: str
    to: str  # a user name, or EVERYBODY
    text: str
    time: str
    at: Revision | None  # the document revision when it was written, to place it in the history

    def to_data(self) -> dict:
        """The plain-data form of the record."""
        return {
            "number": self.number,
            "author": self.author,
            "to": self.to,
            "text": self.text,
            "time": self.time,
            "at": self.at.to_data() if self.at else None,
        }

    @classmethod
    def from_data(cls, data: dict) -> ChatRecord:
        """Inverse of ``to_data``."""
        at = data.get("at")
        return cls(
            data["number"], data["author"], data["to"], data["text"], data["time"], Revision.parse(at) if at else None
        )


@dataclass(frozen=True)
class Ephemeral:
    """A message that is delivered to whoever is connected and then forgotten."""

    kind: str  # "presence", "preview", "typing", ...
    sender: str | None
    data: dict = field(default_factory=dict)

    def to_data(self) -> dict:
        """The plain-data form of the message."""
        return {"kind": self.kind, "sender": self.sender, "data": self.data}


_MENTION = re.compile(r"@(\S+)")


def parse_chat(raw: str, users: Iterable[str] = ()) -> tuple[str, str]:
    """``(recipient, message)`` of what somebody typed into the chat box: ``@username message``.

    Ported from the demo. The recipient is spelled as ``users`` spells it (names may contain spaces, the longest
    name that fits wins, case does not matter). Text without a leading ``@``, or ``@all message``, is for
    everybody. Raises ValueError with a message fit for the user. With no ``users`` given, the first word
    after the ``@`` is taken as the name.
    """
    text = raw.strip()
    if not text:
        raise ValueError("write a message first")
    if not text.startswith("@"):
        return EVERYBODY, _checked(text)
    body = text[1:]
    folded = body.casefold()
    names = sorted(set(users), key=len, reverse=True)
    for name in names:
        n = name.casefold()
        if folded.startswith(n) and (len(body) == len(n) or body[len(n)].isspace() or body[len(n)] in ":,"):
            return name, _checked(body[len(n) :].lstrip(":, \t\r\n"), name)
    word = _MENTION.match(text)
    if word is None:
        raise ValueError("write the name of the person after the @ (@username message), or leave the @ out")
    first = word.group(1).rstrip(":,")
    if first.casefold() in ("all", "everyone", "everybody"):
        return EVERYBODY, _checked(text[word.end() :].lstrip(":, \t\r\n"))
    if not names:
        return first, _checked(text[word.end() :].lstrip(":, \t\r\n"), first)
    who = ", ".join(sorted(names, key=str.casefold))
    raise ValueError(f"{first} is not here. Connected: {who}")


def _checked(message: str, to: str | None = None) -> str:
    message = message.strip()
    if not message:
        raise ValueError(f"write a message after @{to}" if to else "write a message first")
    if len(message) > CHAT_MAX:
        raise ValueError(f"a message can have at most {CHAT_MAX} characters")
    return message
