"""claudia-odf-io: the OpenDocument layer shared by every app's io package (D401).

names      NS, qname, local_name, encode_style_name/decode_style_name -- how ODF names things
splice     XmlPart -- edit one XML part by splicing bytes, so everything outside the edit stays byte-identical
paragraph  read_text/set_text/insert_elements/hidden_content -- the text of one paragraph, changing it in place,
putting change marks between its characters, and what it shows that is not its text
meta       DocumentInfo, new_meta, update_meta, update_package_meta -- title, dates and people of a document
package    new_package, problems -- a package from its parts, and a check that a file is one
report     Loss, LossLog -- what could not be kept, as a list
"""

from ._version import __version__
from .meta import GENERATOR, DocumentInfo, new_meta, odf_date, read_info, update_meta, update_package_meta
from .names import NS, decode_style_name, encode_style_name, local_name, qname
from .package import MIME, VERSION, new_package, problems, read_manifest
from .paragraph import hidden_content, insert_elements, read_text, set_text, xml_safe
from .report import Loss, LossLog
from .splice import OdfError, Span, XmlPart

__all__ = [
    "GENERATOR",
    "MIME",
    "NS",
    "VERSION",
    "DocumentInfo",
    "Loss",
    "LossLog",
    "OdfError",
    "Span",
    "XmlPart",
    "__version__",
    "decode_style_name",
    "encode_style_name",
    "hidden_content",
    "insert_elements",
    "local_name",
    "new_meta",
    "new_package",
    "odf_date",
    "problems",
    "qname",
    "read_info",
    "read_manifest",
    "read_text",
    "set_text",
    "update_meta",
    "update_package_meta",
    "xml_safe",
]
