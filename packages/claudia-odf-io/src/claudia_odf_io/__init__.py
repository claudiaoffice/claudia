"""claudia-odf-io: the OpenDocument layer shared by every app's io package (D401).

names      NS, qname, local_name, encode_style_name/decode_style_name -- how ODF names things
splice     XmlPart -- edit one XML part by splicing bytes, so everything outside the edit stays byte-identical
paragraph  read_text/set_text/insert_elements/hidden_content/frames_of/offset_of -- the text of one paragraph, changing
it in place, putting change marks between its characters, and what it shows that is not its text
pictures   picture_of, name_of, description_of, description_element -- the picture a draw:frame holds and what it says
meta       DocumentInfo, new_meta, update_meta, update_package_meta -- title, dates and people of a document
package    new_package, update_manifest, problems -- a package from its parts, its manifest changed, and a check
language   default_style_xml, read_language, patch_language -- the language of a file, in its default style
report     Loss, LossLog, unwritten_changes -- what could not be kept, as a list, and what a writer left out
transform  inches, transform_of, turned_box, angle_of -- lengths of the format and how a drawing object is turned
fonts      font_faces, font_of -- the font faces of a file and the font a style's text properties name (E3.13)
"""

from ._version import __version__
from .fonts import font_faces, font_of
from .language import (
    NO_LANGUAGE,
    default_style_xml,
    language_from_parts,
    parts_of_language,
    patch_language,
    read_language,
)
from .meta import GENERATOR, DocumentInfo, new_meta, odf_date, read_info, update_meta, update_package_meta
from .names import NS, decode_style_name, encode_style_name, local_name, qname
from .package import MIME, VERSION, new_package, problems, read_manifest, update_manifest
from .paragraph import detach, frames_of, hidden_content, insert_elements, offset_of, read_text, set_text, xml_safe
from .pictures import description_element, description_of, name_of, picture_of
from .report import NOT_WRITTEN, Loss, LossLog, unwritten_changes
from .splice import OdfError, Span, XmlPart
from .transform import angle_of, inches, transform_of, turned_box

__all__ = [
    "GENERATOR",
    "MIME",
    "NOT_WRITTEN",
    "NO_LANGUAGE",
    "NS",
    "VERSION",
    "DocumentInfo",
    "Loss",
    "LossLog",
    "OdfError",
    "Span",
    "XmlPart",
    "__version__",
    "angle_of",
    "decode_style_name",
    "default_style_xml",
    "description_element",
    "detach",
    "font_faces",
    "font_of",
    "description_of",
    "encode_style_name",
    "frames_of",
    "hidden_content",
    "inches",
    "insert_elements",
    "language_from_parts",
    "local_name",
    "new_meta",
    "name_of",
    "new_package",
    "offset_of",
    "odf_date",
    "parts_of_language",
    "picture_of",
    "patch_language",
    "problems",
    "qname",
    "read_info",
    "read_language",
    "read_manifest",
    "read_text",
    "set_text",
    "update_manifest",
    "update_meta",
    "unwritten_changes",
    "update_package_meta",
    "transform_of",
    "turned_box",
    "xml_safe",
]
