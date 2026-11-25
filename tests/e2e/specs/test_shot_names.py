"""Every test keeps its own screenshots (PROC-56).

The screenshots are the evidence when a scenario fails. The examples of one scenario outline share a long name and
differ only at its end, so a name cut short gave them one file, and the next example overwrote the failure's picture.
"""

from conftest import shot_name

OUTLINE = "test_what_one_person_does_to_an_object_a_style_or_the_palette_the_other_sees_at_once"


def test_the_examples_of_one_outline_keep_their_own_screenshots():
    examples = [f"{OUTLINE}[text-insert a picture]", f"{OUTLINE}[workbook-move a container]", f"{OUTLINE}[deck-undo]"]
    assert len({shot_name(example) for example in examples}) == len(examples)


def test_a_screenshot_still_says_which_example_it_shows():
    assert "workbook-move-a-container" in shot_name(f"{OUTLINE}[workbook-move a container]")


def test_a_screenshot_name_stays_short_enough_for_any_file_system():
    assert len(shot_name(f"{OUTLINE}[{'x' * 300}]")) <= 100


def test_a_short_name_is_kept_as_it_was():
    assert shot_name("test_vera_sees_the_text") == "test_vera_sees_the_text"


def test_a_screenshot_name_is_plain_ascii():
    assert shot_name("test_größe_ändert_sich[Übersicht]").isascii()


def test_a_long_example_keeps_the_app_it_is_for():
    assert "workbook-change-a-colour-of-the-palette" in shot_name(f"{OUTLINE}[workbook-change a colour of the palette]")
