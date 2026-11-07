#!/usr/bin/env python3
"""Tiny stand-in for a Claudia document server (E0.3 spike).

Serves /ping and /fonts/ServerFont.ttf on 127.0.0.1 and prints "PORT <n>" on stdout.
With --lifeline it exits when stdin is closed, so a shell can use a pipe as a lifeline (E0.2).
Standard library only.
"""

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STARTED = time.time()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b"", "text/plain")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/ping":
            body = json.dumps({"ok": True, "pid": os.getpid(), "uptime": round(time.time() - STARTED, 3)}).encode()
            self._send(200, body, "application/json")
        elif path == "/fonts/ServerFont.ttf":
            with open(os.path.join(HERE, "fonts", "ServerFont.ttf"), "rb") as f:
                self._send(200, f.read(), "font/ttf")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *args):
        pass


def watch_stdin(server):
    try:
        while sys.stdin.buffer.read(1024):
            pass
    except Exception:
        pass
    server.shutdown()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--lifeline", action="store_true", help="exit when stdin closes (the parent holds the pipe)")
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"PORT {server.server_address[1]}", flush=True)
    if args.lifeline:
        threading.Thread(target=watch_stdin, args=(server,), daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
