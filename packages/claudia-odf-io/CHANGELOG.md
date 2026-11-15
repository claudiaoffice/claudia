# Changelog of claudia-odf-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

## [0.3.0] - 2026-11-15

### Added
- `claudia_odf_io.language` (D461, moved from claudia-composes-io): `default_style_xml`, `read_language`,
  `patch_language`, `language_from_parts`, `parts_of_language`, `NO_LANGUAGE`: the language of an OpenDocument file in the
  default paragraph style. The package depends on claudia-core for the tag check.
- `XmlPart.set_attributes(element, values, remove=())` takes attributes off an element too (an object that is turned
  has no `svg:x`/`svg:y`, one that is not has no `draw:transform`; D459).

### Changed
- `XmlPart` makes the bytes of an inserted or replacing element when the result is made, so that what is done to the
  element until then is in it; `set_attributes` takes the `xml:` prefix (`xml:id`) without a declaration.

## [0.2.0] - 2026-11-14

What a converter does not write is a loss (D450).

### Added
- `unwritten_changes(before, after, *, written, kinds=None)`: the losses for the facets of a model that differ between
  `before` and `after` and that a converter does not write, each as `not-written` with the facet as its detail and how
  many entries differ, or under the code `kinds` gives the facet. `NOT_WRITTEN` is that code.

## [0.1.0] - 2026-11-11

The OpenDocument layer shared by the three apps' io packages (D401): odt, odp and ods (D70).

### Added
- `XmlPart`: edit one XML part by splicing bytes into the original, so everything outside the edited elements stays
  byte for byte what it was (`replace`, `remove`, `insert_before`, `insert_after`, `insert_into`); `Span`, `OdfError`.
- `read_text`, `set_text`, `insert_elements`, `hidden_content`, `xml_safe`: the text of one paragraph, changing it in
  place (links, bookmarks, notes and fields stay where they were), putting change marks between its characters, and
  what it shows that is not its text.
- `new_package`, `problems`, `read_manifest`, `MIME`, `VERSION`: build an OpenDocument package from its parts and check
  that a file is one.
- `NS`, `qname`, `local_name`, `encode_style_name`, `decode_style_name`: how ODF names things.
- `Loss`, `LossLog`: what could not be kept, as codes for the interface to put into words.
- `XmlPart.replace` takes more than one replacement (an element becomes several, D413); `NS` knows `calcext` (cell
  error values) and `of` (OpenFormula, which a file must declare or LibreOffice reads every formula as an error).
- `XmlPart.set_attributes`: change the attributes of one start tag and nothing else of the element (D411, D412).
- `DocumentInfo`, `new_meta`, `update_meta`, `update_package_meta`, `read_info`, `odf_date`, `GENERATOR`: `meta.xml`,
  who made a document and when, written for a new file and kept true in an edited one by splicing, so what the file
  came with (statistics, keywords, user-defined properties) stays; dates are UTC with a `Z` (D411).
