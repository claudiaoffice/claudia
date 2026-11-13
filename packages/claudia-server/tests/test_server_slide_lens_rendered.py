"""The model is told what a rendered container is (D340): a picture made from text, not an unnamed object."""

from claudia_server.slide_lens import describe_object


def test_a_rendered_container_is_named_for_the_model():
    line = describe_object(
        {"id": "o1", "kind": "rendered", "anchor": {"x": 10, "y": 20}, "w": 300, "h": 200, "style": "none"}
    )
    assert line.startswith("o1 rendered text (picture made from text) at (10, 20)")
