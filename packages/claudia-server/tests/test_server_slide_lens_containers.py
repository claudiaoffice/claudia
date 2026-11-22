"""The model is told what a container is (D390): a picture made from text, not an unnamed object."""

from claudia_server.slide_lens import describe_object


def test_a_container_is_named_for_the_model():
    line = describe_object(
        {"id": "o1", "kind": "container", "anchor": {"x": 10, "y": 20}, "w": 300, "h": 200, "style": "none"}
    )
    assert line.startswith("o1 container (a picture made from text, such as a formula or a diagram) at (10, 20)")
