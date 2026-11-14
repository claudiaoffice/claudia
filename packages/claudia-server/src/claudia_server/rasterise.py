"""Drawing an SVG as a PNG, for the office files of a document (D394).

A rendered text container is stored as an SVG, which is what every program should draw: PowerPoint does, LibreOffice
leaves out the colours and text a diagram's style sheet gives. An export that has a rasteriser writes a picture too, so
that it looks right wherever the file is opened. ``rsvg-convert`` (librsvg) is the one used: small, no browser, and it
follows no reference outside the picture.

Called from the synchronous export method, so it is plain ``subprocess`` with a timeout, a clean environment and a
folder of its own; the SVG it is given has passed the render service's allowlist."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable

from claudia_creates_io import Rasterise

PROGRAM = "rsvg-convert"
DENSITY = 2  # pixels per unit of the frame: twice as many as the frame shows, so that it stays sharp when printed
MAX_PIXELS = 4000
TIMEOUT_SECONDS = 20


class RasteriseError(RuntimeError):
    """The picture could not be drawn; the message says why, for the person."""


def svg_rasteriser(program: str | None = None) -> Rasterise | None:
    """A function that draws an SVG as a PNG with ``program`` (default ``rsvg-convert`` on the PATH), or ``None`` if it
    is not there."""
    found = shutil.which(program or PROGRAM)
    if found is None:
        return None
    return _drawing_with(found)


def _drawing_with(program: str) -> Callable[[bytes, int, int], bytes]:
    def draw(svg: bytes, width: int, height: int) -> bytes:
        pixels = max(1, min(MAX_PIXELS, round(width * DENSITY)))
        try:
            with tempfile.TemporaryDirectory() as folder:
                done = subprocess.run(  # noqa: S603 - a program the administrator chose, no shell, arguments fixed
                    [program, "--format", "png", "--width", str(pixels), "--keep-aspect-ratio"],
                    input=svg,
                    capture_output=True,
                    timeout=TIMEOUT_SECONDS,
                    cwd=folder,
                    env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": folder},
                    check=False,
                )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RasteriseError(f"the picture could not be drawn ({error})") from error
        if done.returncode != 0 or not done.stdout.startswith(b"\x89PNG"):
            said = " ".join(done.stderr.decode("utf-8", errors="replace").split())[:200]
            raise RasteriseError(f"the picture could not be drawn: {said or 'no picture came out'}")
        return done.stdout

    return draw
