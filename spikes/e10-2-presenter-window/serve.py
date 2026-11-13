#!/usr/bin/env python3
"""Serves page/ on 127.0.0.1 for the E10.2 spike. No cache, nothing else. Usage: python3 serve.py [port]"""

import functools
import http.server
import pathlib
import sys


class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
root = pathlib.Path(__file__).parent / "page"
srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=str(root)))
print(f"E10.2 spike on http://127.0.0.1:{port}/index.html   (and /frame.html?allow=fullscreen)")
srv.serve_forever()
