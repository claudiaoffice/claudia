"""How an OpenDocument file says its language (D454, D461): the default paragraph style's ``fo:language``,
``fo:script`` and ``fo:country`` in ``styles.xml``. A document with no language is one with ``zxx``, which is what
LibreOffice writes for it.

Shared by every app whose files carry a language (an odt, an odp): writing the default style, reading the tag back and
changing it in a kept file.
"""

from __future__ import annotations

from lxml import etree

from claudia_core import LanguageError, normalize_language

from .names import NS
from .splice import OdfError, XmlPart

#: What a file says when a document has no language: LibreOffice writes "zxx" ("no linguistic content") and "none".
NO_LANGUAGE = ("zxx", "none")


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def language_from_parts(language: str | None, script: str | None, country: str | None) -> str | None:
    """The BCP 47 tag of a file's language, script and country (``"de"``, ``None``, ``"AT"`` -> ``"de-AT"``), or
    ``None`` when it says none or something that is no tag."""
    if not language or language.lower() in NO_LANGUAGE:
        return None
    tag = "-".join(
        part for part in (language, script if script and script.lower() not in NO_LANGUAGE else None) if part
    )
    if country and country.lower() not in NO_LANGUAGE:
        tag += f"-{country}"
    try:
        return normalize_language(tag)
    except LanguageError:
        return None


def parts_of_language(tag: str | None) -> tuple[str, str | None, str | None]:
    """A BCP 47 tag as the language, script and country a file says it with (``"zxx"`` for none); what follows the
    region (variants) is not in the three, as in every office format."""
    if tag is None:
        return NO_LANGUAGE[0], None, None
    language, *rest = tag.split("-")
    script = next((part for part in rest if len(part) == 4 and part.isalpha()), None)
    country = next(
        (part for part in rest if (len(part) == 2 and part.isalpha()) or (len(part) == 3 and part.isdigit())), None
    )
    return language, script, country


def default_style_xml(language: str | None) -> str:
    """The default paragraph style that says ``language``; nothing for a document that has none."""
    if language is None:
        return ""
    name, script, country = parts_of_language(language)
    said = (
        f'fo:language="{name}"'
        + (f' fo:script="{script}"' if script else "")
        + (f' fo:country="{country}"' if country else "")
    )
    return f'<style:default-style style:family="paragraph"><style:text-properties {said}/></style:default-style>'


def _default_style(styles: etree._Element) -> etree._Element | None:
    return next(
        (
            s
            for s in styles.iterfind("office:styles/style:default-style", NS)
            if s.get(_q("style", "family")) == "paragraph"
        ),
        None,
    )


def read_language(styles: etree._Element | None) -> str | None:
    """The language the default paragraph style of ``styles`` (the root of ``styles.xml``) says, or ``None``."""
    default = _default_style(styles) if styles is not None else None
    properties = default.find("style:text-properties", NS) if default is not None else None
    if properties is None:
        return None
    return language_from_parts(
        properties.get(_q("fo", "language")), properties.get(_q("fo", "script")), properties.get(_q("fo", "country"))
    )


def patch_language(part: XmlPart, before: str | None, after: str | None) -> bool:
    """Make the language of the file whose ``styles.xml`` is ``part`` ``after``; did it change anything? An
    :class:`OdfError` when the file has no place for a default style."""
    if before == after:
        return False
    styles = part.root.find("office:styles", NS)
    if styles is None:
        raise OdfError("this file has no default style to give a language")
    default = next(
        (s for s in styles.iterfind("style:default-style", NS) if s.get(_q("style", "family")) == "paragraph"), None
    )
    if default is None:
        if after is not None:
            part.insert_into(styles, default_style_xml(after).encode(), at_start=True)
        return after is not None
    properties = default.find("style:text-properties", NS)
    if properties is None:
        if after is not None:
            part.insert_into(
                default, default_style_xml(after).split(">", 1)[1].rsplit("</style:default-style>", 1)[0].encode()
            )
        return after is not None
    name, script, country = parts_of_language(after)
    values = {"fo:language": name}
    for attribute, value in (("fo:script", script), ("fo:country", country)):
        if value is not None:
            values[attribute] = value
        elif properties.get(_q("fo", attribute.split(":")[1])) is not None:
            values[attribute] = "none"
    part.set_attributes(properties, values)
    return True
