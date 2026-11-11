# Changelog of claudia-odf-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

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
