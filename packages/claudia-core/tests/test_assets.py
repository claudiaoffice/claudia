"""Images: format sniffing, dimension extraction, GIF frames, SVG sanitization, and the import record (E10.8)."""

from __future__ import annotations

import struct

import pytest

from claudia_core.assets import (
    MAX_IMAGE_BYTES,
    ImageAsset,
    ImageError,
    ImageImport,
    decode_image,
)

# ----------------------------------------------------------------------------- building tiny, valid fixtures
_SOF0 = 0xC0


def jpeg_bytes(width: int, height: int) -> bytes:
    """A minimal baseline JPEG: SOI, one SOF0 frame header naming the size, EOI. No real pixels."""
    sof = (
        b"\xff"
        + bytes([_SOF0])
        + struct.pack(">H", 11)
        + bytes([8])
        + struct.pack(">HH", height, width)
        + bytes([1, 1, 0x11, 0])
    )
    return b"\xff\xd8" + sof + b"\xff\xd9"


def bmp_bytes(width: int, height: int, *, top_down: bool = False) -> bytes:
    """A minimal 24-bit uncompressed BMP of ``width`` by ``height``."""
    row = ((width * 3 + 3) // 4) * 4
    pixels = (b"\x00\x00\xff" * width + b"\x00" * (row - width * 3)) * height
    stored_height = -height if top_down else height
    header_size = 14 + 40
    out = b"BM" + struct.pack("<IHHI", header_size + len(pixels), 0, 0, header_size)
    out += struct.pack("<IiiHHIIiiII", 40, width, stored_height, 1, 24, 0, len(pixels), 0, 0, 0, 0)
    return out + pixels


def gif_bytes(width: int, height: int, frames: int = 1) -> bytes:
    """A minimal GIF with a 2-colour global table and ``frames`` tiny images, each with a control extension."""
    header = b"GIF89a" + struct.pack("<HHBBB", width, height, 0x80, 0, 0) + b"\x00\x00\x00\xff\xff\xff"
    frame = b"\x21\xf9\x04\x00\x00\x00\x00\x00"  # graphic control extension (no transparency, no delay)
    frame += b"\x2c" + struct.pack("<HHHH", 0, 0, width, height) + b"\x00"  # image descriptor, no local table
    frame += b"\x02\x01\x00\x00"  # LZW min code size 2, one 1-byte sub-block, terminator
    return header + frame * frames + b"\x3b"


def svg_bytes(width: int = 100, height: int = 50, body: str = "") -> bytes:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">{body}</svg>'.encode()


SAMPLE_JPEG = jpeg_bytes(5, 7)
SAMPLE_GIF = gif_bytes(6, 4)
SAMPLE_SVG = svg_bytes()


# ----------------------------------------------------------------------------- decode_image: dimensions and format
@pytest.mark.parametrize(
    ("data", "fmt", "width", "height"),
    [
        (SAMPLE_JPEG, "jpeg", 5, 7),
        (bmp_bytes(4, 3), "bmp", 4, 3),
        (bmp_bytes(4, 3, top_down=True), "bmp", 4, 3),
        (SAMPLE_GIF, "gif", 6, 4),
        (SAMPLE_SVG, "svg", 100, 50),
    ],
)
def test_decode_image_reads_format_and_size(data, fmt, width, height):
    asset = decode_image(data)
    assert (asset.format, asset.width, asset.height) == (fmt, width, height)
    assert asset.aspect == pytest.approx(width / height)
    if fmt != "svg":  # an SVG is re-serialized after sanitizing, so its byte count need not match the input
        assert asset.size_bytes == len(data)


def test_decode_image_ids_are_content_addressed():
    """The same bytes always get the same id; different bytes (almost always) get a different one."""
    assert decode_image(SAMPLE_JPEG).id == decode_image(bytes(SAMPLE_JPEG)).id
    assert decode_image(SAMPLE_JPEG).id != decode_image(jpeg_bytes(5, 8)).id


def test_decode_image_refuses_unsupported_bytes():
    with pytest.raises(ImageError, match="not a supported image"):
        decode_image(b"%PDF-1.4 not an image")


def test_decode_image_refuses_empty_input():
    with pytest.raises(ImageError):
        decode_image(b"")


def test_decode_image_enforces_the_size_limit():
    oversized = b"\xff\xd8\xff" + b"0" * MAX_IMAGE_BYTES
    with pytest.raises(ImageError, match="at most"):
        decode_image(oversized)


# ----------------------------------------------------------------------------- GIF frames
def test_a_still_gif_is_not_animated_and_keeps_no_first_frame():
    asset = decode_image(gif_bytes(6, 4, frames=1))
    assert asset.animated is False
    assert asset.first_frame is None


def test_a_multi_frame_gif_is_animated_and_its_first_frame_decodes_on_its_own():
    asset = decode_image(gif_bytes(6, 4, frames=3))
    assert asset.animated is True
    assert asset.first_frame is not None
    assert asset.first_frame != asset.data  # it is a strict subset, not a copy
    # the sliced-out first frame is itself a complete, valid still GIF
    still = decode_image(asset.first_frame)
    assert (still.format, still.width, still.height, still.animated) == ("gif", 6, 4, False)


def test_gif_without_an_image_is_refused():
    header = b"GIF89a" + struct.pack("<HHBBB", 1, 1, 0, 0, 0)
    with pytest.raises(ImageError, match="no image"):
        decode_image(header + b"\x3b")


def test_gif_with_a_malformed_data_sub_block_is_refused_not_silently_miscounted():
    # A data sub-block whose length byte claims more bytes than remain must be refused outright. Before this
    # was fixed, the block walk simply ran off the end of the buffer and stopped there: a genuinely 2-frame GIF
    # with its first frame's sub-block corrupted this way silently decoded as a 1-frame, non-animated image
    # (the second frame was never reached) instead of raising ImageError for the malformed input.
    frames = gif_bytes(6, 4, frames=2)
    broken = bytearray(frames)
    sub_block_length_byte = 19 + 8 + 10 + 1  # past header+table, first frame's GCE + image descriptor + LZW-min-code
    assert broken[sub_block_length_byte] == 1  # sanity: this is indeed the one-byte sub-block's length byte
    broken[sub_block_length_byte] = 0xFE  # claims 254 bytes of sub-block data where almost none remain
    with pytest.raises(ImageError, match="truncated data sub-block"):
        decode_image(bytes(broken))


# ----------------------------------------------------------------------------- JPEG/BMP malformed input
def test_jpeg_without_a_frame_header_is_refused():
    with pytest.raises(ImageError, match="no frame header"):
        decode_image(b"\xff\xd8\xff\xd9")  # SOI, EOI, nothing in between


def test_bmp_too_short_is_refused():
    with pytest.raises(ImageError, match="too short"):
        decode_image(b"BM" + b"\x00" * 10)


# ----------------------------------------------------------------------------- SVG sanitization
def test_svg_script_elements_are_removed():
    asset = decode_image(svg_bytes(body="<rect width='1' height='1'/><script>alert(1)</script>"))
    assert b"script" not in asset.data
    assert b"alert" not in asset.data


def test_svg_event_handler_attributes_are_removed():
    asset = decode_image(svg_bytes(body="<circle r='5' onclick='evil()' onload='evil()'/>"))
    assert b"onclick" not in asset.data
    assert b"onload" not in asset.data


def test_svg_external_references_are_removed_but_internal_anchors_survive():
    body = "<a href='https://evil.example/steal'>x</a><use href='#local'/>"
    asset = decode_image(svg_bytes(body=body))
    assert b"evil.example" not in asset.data


def test_svg_foreign_object_and_iframe_are_removed():
    asset = decode_image(svg_bytes(body="<foreignObject><iframe src='https://evil.example'/></foreignObject>"))
    assert b"foreignObject" not in asset.data
    assert b"iframe" not in asset.data
    assert b"evil.example" not in asset.data


@pytest.mark.parametrize(
    "payload",
    [
        b'<?xml version="1.0"?><!DOCTYPE svg><svg width="1" height="1"/>',
        b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x "boom">]><svg width="1" height="1">&x;</svg>',
        b'<!ENTITY x "boom"><svg width="1" height="1"/>',
    ],
)
def test_svg_doctype_and_entity_declarations_are_rejected_outright(payload):
    with pytest.raises(ImageError, match="DOCTYPE or ENTITY"):
        decode_image(payload)


def test_svg_doctype_past_the_old_scan_window_is_still_rejected():
    # The DOCTYPE/ENTITY check must see the whole file, not just an early prefix: padding the file with an
    # innocuous comment before the DOCTYPE must not let an entity-expansion payload reach the XML parser.
    padding = f"<!-- {'x' * 2100} -->"
    payload = (
        '<?xml version="1.0"?>' + padding + '<!DOCTYPE svg [<!ENTITY x "boom">]><svg width="1" height="1">&x;</svg>'
    ).encode()
    with pytest.raises(ImageError, match="DOCTYPE or ENTITY"):
        decode_image(payload)


def test_svg_root_must_be_svg():
    # sniffing sees "<svg" in there and treats it as a candidate SVG; parsing must still refuse a root that is not <svg>
    with pytest.raises(ImageError, match="root element must be"):
        decode_image(b'<html xmlns="http://www.w3.org/1999/xhtml"><svg xmlns="http://www.w3.org/2000/svg"/></html>')


def test_svg_not_well_formed_is_refused():
    with pytest.raises(ImageError, match="well-formed"):
        decode_image(b"<svg width='1' height='1'><rect>")  # unclosed


def test_svg_size_falls_back_to_viewbox_when_width_and_height_are_absent():
    asset = decode_image(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 80"/>')
    assert (asset.width, asset.height) == (40, 80)


def test_svg_without_any_usable_size_is_refused():
    with pytest.raises(ImageError, match="no positive width and height"):
        decode_image(b'<svg xmlns="http://www.w3.org/2000/svg"/>')


def test_svg_output_keeps_the_plain_xmlns_form_not_an_invented_prefix():
    asset = decode_image(SAMPLE_SVG)
    assert b'xmlns="http://www.w3.org/2000/svg"' in asset.data
    assert b"ns0:" not in asset.data


# ----------------------------------------------------------------------------- ImageAsset: to_data / from_data
def test_image_asset_round_trips_through_plain_data():
    asset = decode_image(gif_bytes(6, 4, frames=2))
    restored = ImageAsset.from_data(asset.to_data())
    assert restored == asset


def test_image_asset_to_data_is_json_safe():
    """``data`` and ``first_frame`` must be plain strings: the snapshot and the wire protocol are JSON."""
    asset = decode_image(gif_bytes(6, 4, frames=2))
    data = asset.to_data()
    assert isinstance(data["data"], str)
    assert isinstance(data["first_frame"], str)
    import json

    json.dumps(data)  # raises if anything is not JSON-compatible


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (
            {
                "id": "not-hex",
                "format": "jpeg",
                "width": 1,
                "height": 1,
                "animated": False,
                "data": "AA==",
                "first_frame": None,
            },
            "sha256",
        ),
        (
            {
                "id": "a" * 64,
                "format": "tiff",
                "width": 1,
                "height": 1,
                "animated": False,
                "data": "AA==",
                "first_frame": None,
            },
            "format",
        ),
        (
            {
                "id": "a" * 64,
                "format": "jpeg",
                "width": 0,
                "height": 1,
                "animated": False,
                "data": "AA==",
                "first_frame": None,
            },
            "whole numbers",
        ),
        (
            {
                "id": "a" * 64,
                "format": "jpeg",
                "width": 1,
                "height": 1,
                "animated": "yes",
                "data": "AA==",
                "first_frame": None,
            },
            "true or false",
        ),
        (
            {
                "id": "a" * 64,
                "format": "jpeg",
                "width": 1,
                "height": 1,
                "animated": False,
                "data": "not base64!",
                "first_frame": None,
            },
            "base64",
        ),
    ],
)
def test_image_asset_from_data_rejects_bad_values(bad, message):
    with pytest.raises(ImageError, match=message):
        ImageAsset.from_data(bad)


def test_image_asset_from_data_enforces_the_size_limit_too():
    # decode_image() checks MAX_IMAGE_BYTES before doing any decode work, but from_data() is a separate path
    # (replaying a command log, loading a document from storage) that bypasses decode_image() entirely. It must
    # enforce the same cap on the bytes it base64-decodes, or that cap is not a real limit at all on this path.
    import base64
    import hashlib

    huge = b"0" * (MAX_IMAGE_BYTES + 1)
    data = {
        "id": hashlib.sha256(huge).hexdigest(),
        "format": "bmp",
        "width": 1,
        "height": 1,
        "animated": False,
        "data": base64.b64encode(huge).decode("ascii"),
        "first_frame": None,
    }
    with pytest.raises(ImageError, match="at most"):
        ImageAsset.from_data(data)


def test_image_asset_from_data_enforces_the_size_limit_on_first_frame_too():
    # first_frame is attacker-controlled independently of data when from_data() is called directly (not through
    # decode_image(), which always derives it from an already-capped source), so it needs its own bound.
    import base64
    import hashlib

    small, huge = b"0", b"1" * (MAX_IMAGE_BYTES + 1)
    data = {
        "id": hashlib.sha256(small).hexdigest(),
        "format": "bmp",
        "width": 1,
        "height": 1,
        "animated": True,
        "data": base64.b64encode(small).decode("ascii"),
        "first_frame": base64.b64encode(huge).decode("ascii"),
    }
    with pytest.raises(ImageError, match="at most"):
        ImageAsset.from_data(data)


def test_image_asset_from_data_requires_every_field():
    with pytest.raises(ImageError, match="needs"):
        ImageAsset.from_data({"id": "a" * 64, "format": "jpeg"})


# ----------------------------------------------------------------------------- ImageImport
def make_import(**overrides) -> ImageImport:
    fields = {
        "asset": "a" * 64,
        "alt": "a quarterly growth chart",
        "imported_by": "sofia",
        "imported_at": "2026-11-07T10:00:00.000Z",
        "source": "disk",
        "source_name": "quarterly-growth.svg",
        "source_path": "/Users/sofia/Documents/charts/quarterly-growth.svg",
    }
    fields.update(overrides)
    return ImageImport(**fields)


def test_image_import_round_trips_through_plain_data():
    record = make_import()
    assert ImageImport.from_data(record.to_data()) == record


def test_image_import_masks_the_source_path_from_everyone_but_the_importer():
    record = make_import()
    for_colleague = record.masked("ben")
    assert for_colleague.source_path is None
    assert for_colleague.source == "disk"  # that it came from disk is not hidden, only where on disk
    assert for_colleague.source_name == record.source_name
    assert for_colleague.imported_by == "sofia"  # who imported it is not hidden either

    assert record.masked("sofia") == record  # the importer still sees their own path


def test_image_import_masking_is_a_no_op_when_there_is_no_path_to_hide():
    record = make_import(source_path=None)
    assert record.masked("ben") == record


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"alt": ""}, "needs a short description"),
        ({"alt": "x" * 400}, "at most"),
        ({"source": "usb-stick"}, "'disk' or 'clipboard'"),
        ({"source_path": 5}, "source_path"),
    ],
)
def test_image_import_from_data_rejects_bad_values(overrides, message):
    data = make_import(**{k: v for k, v in overrides.items() if k != "source_path" or v is None}).to_data()
    data.update(overrides)
    with pytest.raises(ImageError, match=message):
        ImageImport.from_data(data)


def test_image_import_from_data_rejects_unknown_or_missing_fields():
    with pytest.raises(ImageError, match="exactly these fields"):
        ImageImport.from_data({**make_import().to_data(), "extra": "nope"})
    with pytest.raises(ImageError, match="exactly these fields"):
        ImageImport.from_data({"asset": "a" * 64})
