"""A second, plain-HTTP port that only sends people to the secure one.

Somebody who types ``claudia.example.org:8765`` or ``http://...`` into a browser reaches a server that speaks TLS and
gets nothing but an error. With ``--redirect-port`` (in a container: the port published as 80, say) such a request is
answered with "moved permanently: use https://same-host:secure-port/same-path". Nothing else is served there, and
nothing that arrives in plain text is ever used.
"""

from __future__ import annotations

import asyncio
import re
import threading

_HOST = re.compile(r"(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)(?::\d+)?")
_TARGET = re.compile(r"/[\x21-\x7e]*")  # (printable ASCII, no spaces or control characters: no header injection)


def location_for(request_head: bytes, secure_port: int, fallback_host: str) -> str:
    """The https address a plain-HTTP request should be sent to."""
    lines = request_head.decode("latin-1").split("\r\n")
    parts = lines[0].split(" ")
    target = parts[1] if len(parts) >= 2 and _TARGET.fullmatch(parts[1]) else "/"
    host = fallback_host
    for line in lines[1:]:
        name, _, value = line.partition(":")
        if name.strip().lower() == "host":
            found = _HOST.fullmatch(value.strip())
            if found:
                host = found.group(1)
            break
    port = "" if secure_port == 443 else f":{secure_port}"
    return f"https://{host}{port}{target}"


async def _serve(host: str, port: int, secure_port: int, ready: threading.Event, failed: list) -> None:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
            where = location_for(head, secure_port, "localhost")
            body = f"This server is only reachable over a secure connection: {where}\n".encode()
            writer.write(
                b"HTTP/1.1 301 Moved Permanently\r\nLocation: "
                + where.encode("ascii", "replace")
                + b"\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + body
            )
            await writer.drain()
        except TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError:
            pass
        finally:
            writer.close()

    try:
        server = await asyncio.start_server(handle, host, port)
    except OSError as exc:
        failed.append(exc)
        ready.set()
        return
    ready.set()
    async with server:
        await server.serve_forever()


def start(host: str, port: int, secure_port: int) -> None:
    """Run the redirecting listener in a thread of its own (it ends with the program). ``OSError`` if the port is
    taken."""
    ready, failed = threading.Event(), list[OSError]()
    threading.Thread(
        target=lambda: asyncio.run(_serve(host, port, secure_port, ready, failed)), daemon=True, name="http-redirect"
    ).start()
    ready.wait(5)
    if failed:
        raise failed[0]
