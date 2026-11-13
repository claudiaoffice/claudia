"""What makes the Linux client *one of the three apps* to the desktop: id, desktop entry, icon, AppStream data,
start command (D97)."""

from __future__ import annotations

import configparser
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from claudia_shell_gtk import identity, manifest

APPS = Path(identity.__file__).resolve().parents[2] / "apps"


def test_the_application_id_is_lower_case_without_underscores_as_decided() -> None:
    composes = identity.get("composes")
    assert composes.application_id == "de.claudiaoffice.composes"
    assert re.fullmatch(r"[a-z]+(\.[a-z]+)+", composes.application_id)


def test_the_app_names_the_server_model_it_hosts() -> None:
    assert identity.get("composes").model == "claudia_composes:TextModel"


@pytest.mark.parametrize(
    ("app", "model"),
    [
        ("composes", "claudia_composes:TextModel"),
        ("computes", "claudia_computes:WorkbookModel"),
        ("creates", "claudia_creates:SlideModel"),
    ],
)
def test_every_app_has_its_own_application_id_and_server_model(app: str, model: str) -> None:
    """The three apps are told apart by the identity alone: nothing else in the shell names one of them (D97)."""
    found = identity.get(app)
    assert found.application_id == f"de.claudiaoffice.{app}"
    assert found.model == model


def test_an_unknown_app_is_a_clear_error() -> None:
    try:
        identity.get("drawbook")  # never was, never will be — the point is only that no such name exists
    except identity.UnknownApp as problem:
        assert "composes" in str(problem)  # it says what is available
    else:
        raise AssertionError("drawbook has no Linux client")


LINUX = Path(identity.__file__).resolve().parents[2]
EXPECTED = {
    "composes": ("Claudia Composes", "WordProcessor"),
    "computes": ("Claudia Computes", "Spreadsheet"),
    "creates": ("Claudia Creates", "Presentation"),
}
APP_NAMES = tuple(EXPECTED)


def test_the_apps_are_exactly_the_three_of_the_suite() -> None:
    assert identity.names() == APP_NAMES


@pytest.mark.parametrize("app", APP_NAMES)
def test_the_command_is_named_after_the_app(app: str) -> None:
    assert identity.get(app).command == f"claudia-{app}"


@pytest.mark.parametrize("app", APP_NAMES)
def test_every_app_has_a_manifest_and_a_matching_identity(app: str) -> None:
    assert manifest.for_app(app).app == identity.get(app).name == app


def desktop_entry(app: str) -> configparser.ConfigParser:
    entry = configparser.ConfigParser(interpolation=None)
    entry.optionxform = str  # type: ignore[assignment,method-assign]  # keys are case sensitive
    entry.read(APPS / app / f"de.claudiaoffice.{app}.desktop", encoding="utf-8")
    return entry


@pytest.mark.parametrize("app", APP_NAMES)
def test_the_desktop_entry_is_named_after_the_application_id_and_starts_the_shell(app: str) -> None:
    title, category = EXPECTED[app]
    section = desktop_entry(app)["Desktop Entry"]
    assert section["Type"] == "Application"
    assert section["Name"] == title
    assert section["Exec"] == f"claudia-{app}"
    assert section["Icon"] == f"de.claudiaoffice.{app}"
    assert section["StartupWMClass"] == f"de.claudiaoffice.{app}"
    assert section["Terminal"] == "false"
    categories = section["Categories"].split(";")
    assert {"Office", "GTK", category} <= set(categories)


@pytest.mark.parametrize("app", APP_NAMES)
def test_the_icon_is_in_the_theme_layout_under_the_application_id(app: str) -> None:
    icon = APPS / app / "icons" / "hicolor" / "scalable" / "apps" / f"de.claudiaoffice.{app}.svg"
    root = ET.parse(icon).getroot()
    assert root.tag.endswith("svg")
    assert identity.get(app).icon_search_path == APPS / app / "icons"


@pytest.mark.parametrize("app", APP_NAMES)
def test_the_appstream_file_agrees_with_the_application_id_and_the_licence(app: str) -> None:
    root = ET.parse(APPS / app / f"de.claudiaoffice.{app}.metainfo.xml").getroot()
    assert root.findtext("id") == f"de.claudiaoffice.{app}"
    assert root.findtext("project_license") == "GPL-3.0-or-later"
    assert root.findtext("launchable") == f"de.claudiaoffice.{app}.desktop"
    assert root.get("type") == "desktop-application"
    assert root.findtext("name") == EXPECTED[app][0]


@pytest.mark.parametrize("app", APP_NAMES)
def test_every_app_has_a_command_that_starts_that_app(app: str) -> None:
    """A person gets one start button per app (the .desktop file) and the command it names has to exist (D97)."""
    scripts = tomllib.loads((LINUX / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    assert scripts[identity.get(app).command] == f"claudia_shell_gtk.__main__:{app}"


@pytest.mark.parametrize("app", APP_NAMES)
def test_the_icon_is_the_one_of_the_web_app(app: str) -> None:
    """One icon per app everywhere (design system, section 4): the shapes of the desktop icon are those of
    ``web/app/components/AppIcon.vue``, so the launcher and the web app never drift apart."""
    import re

    vue = (LINUX.parent.parent / "web" / "app" / "components" / "AppIcon.vue").read_text(encoding="utf-8")
    block = re.search(rf'aria-label="{app}">(.*?)</svg>', vue, re.DOTALL)
    assert block is not None
    icon = (APPS / app / "icons" / "hicolor" / "scalable" / "apps" / f"de.claudiaoffice.{app}.svg").read_text(
        encoding="utf-8"
    )
    for attribute in re.findall(r'(?:d|fill|stroke)="([^"]+)"', block.group(1)):
        assert attribute in icon, f"{attribute!r} of the web icon is missing from the desktop icon"
