"""The shape library: shapes are plain JSON files that users can add to (D67, E10.7)."""

import json

import pytest

from claudia_creates import ShapeDefinition, ShapeError, ShapeLibrary, parse_shape

RECTANGLE = {
    "format": 1,
    "id": "rectangle",
    "name": "Rectangle",
    "path": "M0 0 L100 0 L100 100 L0 100 Z",
}


def shape_json(**changes) -> str:
    data = {**RECTANGLE, **changes}
    return json.dumps({k: v for k, v in data.items() if v is not ...})


def write(folder, name: str, text: str):
    (folder / name).write_text(text, encoding="utf-8")


# -- reading one shape --------------------------------------------------------------------------------------------
def test_a_minimal_shape_gets_sensible_defaults():
    shape = parse_shape(shape_json())
    assert shape.id == "rectangle" and shape.name == "Rectangle"
    assert shape.aspect is None, "a shape is free to be stretched unless it says otherwise"
    assert shape.text_area == (0, 0, 100, 100), "text goes into the whole box unless the shape says where"


def test_a_shape_round_trips_through_its_plain_data():
    shape = parse_shape(shape_json(aspect=1, text_area={"x": 15, "y": 15, "w": 70, "h": 70}))
    assert ShapeDefinition.from_data(shape.to_data()) == shape
    assert shape.to_data()["format"] == 1
    assert json.loads(json.dumps(shape.to_data())) == shape.to_data(), "plain data: it must survive JSON"


def test_path_separators_may_be_spaces_commas_or_nothing_at_all():
    for path in ("M0 0L100 0L100 100L0 100Z", "M 0,0 L 100,0 L 100,100 L 0,100 Z", "M0,0 L100,0 L100,100 L0,100 Z"):
        assert parse_shape(shape_json(path=path)).path == path


def test_every_path_command_is_accepted_with_its_numbers():
    path = "M10 10 L90 10 C90 40 60 60 50 90 A30 30 0 0 1 10 90 Z"
    assert parse_shape(shape_json(path=path)).path == path


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"id": "Rectangle"}, "id"),
        ({"id": ""}, "id"),
        ({"id": "x" * 41}, "id"),
        ({"id": "1rect"}, "id"),
        ({"name": ""}, "name"),
        ({"name": "  "}, "name"),
        ({"name": "n" * 61}, "name"),
        ({"format": 2}, "format"),
        ({"format": ...}, "format"),
        ({"path": ""}, "path"),
        ({"path": "L0 0 L100 100"}, "start with M"),
        ({"path": "M0 0 l10 10"}, "path"),
        ({"path": "M0 0 H50"}, "path"),
        ({"path": "M0 0 L100"}, "path"),
        ({"path": "M0 0 L100 100 50"}, "path"),
        ({"path": "M0 0 L101 100"}, "path"),
        ({"path": "M0 0 L-1 100"}, "path"),
        ({"path": "M0 0 L1e2 100"}, "path"),
        ({"path": "M0 0 A50 50 0 2 1 50 100"}, "path"),
        ({"path": "M0 0 A50 50 0 1 1 50"}, "path"),
        ({"path": "M0 0 " + "L1 1 " * 2000}, "path"),
        ({"path": 7}, "path"),
        ({"aspect": 0}, "aspect"),
        ({"aspect": -1}, "aspect"),
        ({"aspect": 11}, "aspect"),
        ({"aspect": True}, "aspect"),
        ({"aspect": "square"}, "aspect"),
        ({"text_area": {"x": 0, "y": 0, "w": 0, "h": 50}}, "text_area"),
        ({"text_area": {"x": 60, "y": 0, "w": 50, "h": 50}}, "text_area"),
        ({"text_area": {"x": 0, "y": 0, "w": 50}}, "text_area"),
        ({"text_area": [0, 0, 50, 50]}, "text_area"),
    ],
)
def test_a_shape_that_is_not_right_is_refused_with_a_sentence_that_says_where(changes, message):
    with pytest.raises(ShapeError, match=message):
        parse_shape(shape_json(**changes))


def test_text_that_is_not_a_shape_is_refused():
    for text in ("", "not json", "[]", "7", "null", '{"format": 1}'):
        with pytest.raises(ShapeError):
            parse_shape(text)


def test_an_unknown_key_is_refused_so_that_typos_are_noticed():
    with pytest.raises(ShapeError, match="colour"):
        parse_shape(shape_json(colour="red"))


def test_a_shape_carries_no_script_or_style_only_geometry():
    """The format has no place for anything but an outline: styles come from the document's styles (D73)."""
    for key in ("fill", "stroke", "style", "script", "href"):
        with pytest.raises(ShapeError):
            parse_shape(shape_json(**{key: "x"}))


# -- the library --------------------------------------------------------------------------------------------------
def test_the_library_ships_a_rectangle_a_circle_and_a_triangle():
    library = ShapeLibrary.load()
    assert [s.id for s in library] == ["circle", "rectangle", "triangle"]
    assert library.problems == ()
    assert library.get("circle").aspect == 1, "a circle stays a circle"
    assert library.get("rectangle").aspect is None
    assert library.get("triangle").aspect is None


def test_the_shipped_shapes_are_valid_and_inside_their_box():
    for shape in ShapeLibrary.load():
        assert ShapeDefinition.from_data(shape.to_data()) == shape
        assert shape.name


def test_an_unknown_shape_is_none_and_membership_works():
    library = ShapeLibrary.load()
    assert library.get("hexagon") is None
    assert "circle" in library and "hexagon" not in library
    assert len(library) == 3


def test_a_folder_of_json_files_adds_shapes(tmp_path):
    write(tmp_path, "star.json", shape_json(id="star", name="Star", path="M50 0 L61 35 L98 35 L68 57 Z"))
    library = ShapeLibrary.load([tmp_path])
    assert [s.id for s in library] == ["circle", "rectangle", "star", "triangle"]
    assert library.get("star").name == "Star"
    assert library.problems == ()


def test_a_later_folder_wins_over_an_earlier_one_and_over_the_shipped_shapes(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    write(first, "rectangle.json", shape_json(name="Box"))
    write(second, "rectangle.json", shape_json(name="Plate"))
    assert ShapeLibrary.load([first]).get("rectangle").name == "Box"
    assert ShapeLibrary.load([first, second]).get("rectangle").name == "Plate"


def test_a_file_that_is_not_right_is_skipped_and_reported_not_fatal(tmp_path):
    write(tmp_path, "good.json", shape_json(id="good", name="Good"))
    write(tmp_path, "broken.json", "{ not json")
    write(tmp_path, "wrong-colour.json", shape_json(id="wrong-colour", colour="red"))
    library = ShapeLibrary.load([tmp_path])
    assert "good" in library and "broken" not in library
    assert dict(library.problems).keys() == {"broken.json", "wrong-colour.json"}
    assert all(message for _, message in library.problems)


def test_the_file_name_must_say_which_shape_it_holds(tmp_path):
    write(tmp_path, "oval.json", shape_json(id="ellipse", name="Ellipse"))
    library = ShapeLibrary.load([tmp_path])
    assert "ellipse" not in library
    assert dict(library.problems)["oval.json"].startswith("the file name"), "so that two files cannot fight over an id"


def test_files_that_are_not_json_are_left_alone(tmp_path):
    write(tmp_path, "notes.txt", "my shapes")
    write(tmp_path, "README.md", "# shapes")
    assert ShapeLibrary.load([tmp_path]).problems == ()


def test_a_huge_file_is_refused_without_being_read_in_full(tmp_path):
    write(tmp_path, "huge.json", shape_json(id="huge", name="x" * 100_000))
    library = ShapeLibrary.load([tmp_path])
    assert "huge" not in library
    assert "too large" in dict(library.problems)["huge.json"]


def test_a_folder_that_does_not_exist_is_a_problem_not_a_crash(tmp_path):
    library = ShapeLibrary.load([tmp_path / "nowhere"])
    assert len(library) == 3
    assert [name for name, _ in library.problems] == ["nowhere"]
