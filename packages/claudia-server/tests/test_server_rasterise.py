"""Drawing an SVG as a PNG for office files, where a program cannot draw the SVG itself (D394)."""

import shutil
import struct

import pytest

from claudia_server.rasterise import RasteriseError, svg_rasteriser

SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="30" height="10">'
    b'<rect width="30" height="10" fill="#c81e1e"/></svg>'
)
needs_rsvg = pytest.mark.skipif(shutil.which("rsvg-convert") is None, reason="rsvg-convert is not installed")


def png_size(data: bytes) -> tuple[int, int]:
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", data[16:24])


def test_there_is_no_rasteriser_where_the_program_is_not_found(tmp_path):
    assert svg_rasteriser(str(tmp_path / "nowhere" / "rsvg-convert")) is None


@needs_rsvg
def test_an_svg_is_drawn_twice_as_wide_as_its_frame_so_that_it_stays_sharp():
    draw = svg_rasteriser()
    assert draw is not None
    assert png_size(draw(SVG, 300, 100)) == (600, 200)


@needs_rsvg
def test_the_picture_is_never_larger_than_a_screen_can_use():
    assert png_size(svg_rasteriser()(SVG, 90_000, 30_000))[0] <= 4000


@needs_rsvg
def test_a_picture_that_is_not_an_svg_is_refused_with_a_sentence_and_does_not_hang():
    with pytest.raises(RasteriseError):
        svg_rasteriser()(b"not a picture", 100, 100)


def test_a_program_that_fails_is_reported(tmp_path):
    fake = tmp_path / "rsvg-convert"
    fake.write_text("#!/bin/sh\necho broken >&2\nexit 3\n")
    fake.chmod(0o755)
    with pytest.raises(RasteriseError, match="broken"):
        svg_rasteriser(str(fake))(SVG, 10, 10)
