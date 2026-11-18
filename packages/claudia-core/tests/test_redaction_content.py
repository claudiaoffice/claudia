"""What counts as content when a step is redacted (D720): words, descriptions, the words of an import record and the
pixels of a picture go; ids, sizes and places stay."""

from claudia_core import AddObject, DefineImage, ImageImport, ObjectBody, decode_image, paragraph_for
from claudia_core.assets import BLANK_GIF, ImageAsset
from claudia_core.objects import FILLER, blank_body

PIXELS = b"\x89PNG secret pixels"


def asset() -> ImageAsset:
    return ImageAsset("ab" * 32, "png", 640, 480, False, PIXELS)


def picture_import() -> ImageImport:
    return ImageImport("ab" * 32, "our new logo", "ana", "2026-11-16T10:00:00.000Z", "disk", "logo-v2.png", "/home/ana")


def test_a_redacted_picture_keeps_its_id_and_size_but_not_its_pixels():
    blank = asset().blanked()
    assert (blank.id, blank.width, blank.height) == (asset().id, 640, 480)
    assert blank.data == BLANK_GIF and not blank.animated and blank.first_frame is None
    seen = decode_image(BLANK_GIF)
    assert (seen.format, seen.width, seen.height) == ("gif", 1, 1)


def test_redacting_the_step_that_took_a_picture_in_blanks_the_picture():
    redacted = DefineImage(asset()).redacted()
    assert isinstance(redacted, DefineImage) and redacted.image.data == BLANK_GIF


def test_an_import_record_keeps_who_and_when_but_not_what_was_written_or_where_it_came_from():
    blank = picture_import().blanked()
    assert (blank.alt, blank.source_name, blank.source_path) == ("", "", None)
    assert (blank.imported_by, blank.imported_at, blank.source) == ("ana", "2026-11-16T10:00:00.000Z", "disk")


def test_a_redacted_object_loses_its_words_its_description_and_its_import_words():
    body = ObjectBody(
        "i1", "image", 40, 30, "plain-image", ref="ab" * 32, imported=picture_import(), description="the CEO's face"
    )
    command = AddObject(body, {"container": "s1"}).redacted()
    assert command.body.description == "" and command.body.imported.alt == ""
    assert command.body.imported.source_name == "" and command.body.image == "ab" * 32


def test_blanking_a_text_box_in_place_keeps_its_length():
    box = ObjectBody("t1", "text", 100, 40, "body-text", paragraph=paragraph_for("t1", "body-text", "pin 1234"))
    assert blank_body(box, keep_length=True).paragraph.text == FILLER * 8
    assert blank_body(box).paragraph.text == ""
