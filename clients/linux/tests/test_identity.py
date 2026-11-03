"""What makes the Linux client *claudia composes* to the desktop: id, desktop entry, icon, AppStream data."""

from __future__ import annotations

import configparser
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from claudia_shell_gtk import identity

APPS = Path(identity.__file__).resolve().parents[2] / "apps"


def test_the_application_id_is_lower_case_without_underscores_as_decided() -> None:
    composes = identity.get("composes")
    assert composes.application_id == "de.claudiaoffice.composes"
    assert re.fullmatch(r"[a-z]+(\.[a-z]+)+", composes.application_id)


def test_the_app_names_the_server_model_it_hosts() -> None:
    assert identity.get("composes").model == "claudia_composes:TextModel"


def test_an_unknown_app_is_a_clear_error() -> None:
    try:
        identity.get("computes")
    except identity.UnknownApp as problem:
        assert "composes" in str(problem)  # it says what is available
    else:
        raise AssertionError("computes has no Linux client yet")


def desktop_entry() -> configparser.ConfigParser:
    entry = configparser.ConfigParser(interpolation=None)
    entry.optionxform = str  # type: ignore[assignment,method-assign]  # keys are case sensitive
    entry.read(APPS / "composes" / "de.claudiaoffice.composes.desktop", encoding="utf-8")
    return entry


def test_the_desktop_entry_is_named_after_the_application_id_and_starts_the_shell() -> None:
    section = desktop_entry()["Desktop Entry"]
    assert section["Type"] == "Application"
    assert section["Name"] == "Claudia Composes"
    assert section["Exec"] == "claudia-composes"
    assert section["Icon"] == "de.claudiaoffice.composes"
    assert section["Terminal"] == "false"
    assert "Office" in section["Categories"].split(";")
    assert "GTK" in section["Categories"].split(";")


def test_the_icon_is_in_the_theme_layout_under_the_application_id() -> None:
    icon = APPS / "composes" / "icons" / "hicolor" / "scalable" / "apps" / "de.claudiaoffice.composes.svg"
    root = ET.parse(icon).getroot()
    assert root.tag.endswith("svg")
    assert identity.get("composes").icon_search_path == APPS / "composes" / "icons"


def test_the_appstream_file_agrees_with_the_application_id_and_the_licence() -> None:
    root = ET.parse(APPS / "composes" / "de.claudiaoffice.composes.metainfo.xml").getroot()
    assert root.findtext("id") == "de.claudiaoffice.composes"
    assert root.findtext("project_license") == "GPL-3.0-or-later"
    assert root.findtext("launchable") == "de.claudiaoffice.composes.desktop"
    assert root.get("type") == "desktop-application"
    assert root.findtext("name") == "Claudia Composes"
