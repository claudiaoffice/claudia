"""claudia-odf-io: the OpenDocument layer shared by every app's io package (D401).

names      NS, qname, local_name, encode_style_name/decode_style_name -- how ODF names things
splice     XmlPart -- edit one XML part by splicing bytes, so everything outside the edit stays byte-identical
paragraph  read_text/set_text/insert_elements/hidden_content -- the text of one paragraph, changing it in place,
putting change marks between its characters, and what it shows that is not its text
package    new_package, problems -- a package from its parts, and a check that a file is one
report     Loss, LossLog -- what could not be kept, as a list
"""

from ._version import __version__
from .names import NS, decode_style_name, encode_style_name, local_name, qname
from .package import MIME, VERSION, new_package, problems, read_manifest
from .paragraph import hidden_content, insert_elements, read_text, set_text, xml_safe
from .report import Loss, LossLog
from .splice import OdfError, Span, XmlPart

__all__ = [
    "MIME",
    "NS",
    "VERSION",
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
    "new_package",
    "problems",
    "qname",
    "read_manifest",
    "read_text",
    "set_text",
    "xml_safe",
]
