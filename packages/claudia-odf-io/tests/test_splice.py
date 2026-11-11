"""XmlPart: edit one XML part by splicing bytes, so that everything outside the edit is the original, byte for byte.

This is the preservation promise of D401. A tree library's own serialisation changes bytes nobody edited (``&apos;``
becomes ``'``, the quotes of the declaration change); an ODF file keeps every sheet, slide and paragraph in one
``content.xml``, so there is no "untouched part" to fall back on, as there is for xlsx and pptx (D219, D220)."""

from __future__ import annotations

import pytest
from lxml import etree

from claudia_odf_io import NS, OdfError, XmlPart

HEAD = b'<?xml version="1.0" encoding="UTF-8"?>\n'
DOC = (
    HEAD
    + b'<o:doc xmlns:o="urn:o" xmlns:t="urn:t" xmlns:x="urn:x">'
    + b'<o:body f="&apos;Liberation Sans&apos;">'
    + b'<t:p a="1 &gt; 0">one</t:p>'
    + b"<t:p b='say \"hi\" > bye'>two <t:span>and</t:span> more</t:p>"
    + b"<t:p/>"
    + b"<t:list><t:item><t:p>deep</t:p></t:item></t:list>"
    + b"</o:body></o:doc>"
)


def paragraphs(part: XmlPart):
    return [el for el in part.elements() if el.tag == "{urn:t}p"]


# -- nothing edited, nothing changed -------------------------------------------------------------------------
def test_without_edits_the_bytes_are_the_original_bytes():
    assert XmlPart(DOC).result() == DOC


def test_the_entities_and_the_declaration_of_the_original_are_not_normalised_away():
    out = XmlPart(DOC).result()
    assert b"&apos;Liberation Sans&apos;" in out and out.startswith(b'<?xml version="1.0"')


# -- where an element is -------------------------------------------------------------------------------------
def test_every_element_has_a_span_that_is_exactly_its_own_markup():
    part = XmlPart(DOC)
    first, second, empty, deep = paragraphs(part)
    cut = lambda el: DOC[slice(*part.span(el))]  # noqa: E731
    assert cut(first) == b'<t:p a="1 &gt; 0">one</t:p>'
    assert cut(second) == b"<t:p b='say \"hi\" > bye'>two <t:span>and</t:span> more</t:p>"  # a ">" inside a value
    assert cut(empty) == b"<t:p/>"
    assert cut(deep) == b"<t:p>deep</t:p>"


def test_the_whole_document_element_spans_the_whole_body_of_the_file():
    part = XmlPart(DOC)
    start, end = part.span(part.root)
    assert DOC[start:end] == DOC[len(HEAD) :]


# -- edits ---------------------------------------------------------------------------------------------------
def test_replace_changes_only_the_bytes_of_that_element():
    part = XmlPart(DOC)
    first = paragraphs(part)[0]
    part.replace(first, part.make("t:p", text="ONE"))
    assert part.result() == DOC.replace(b'<t:p a="1 &gt; 0">one</t:p>', b"<t:p>ONE</t:p>")


def test_replace_with_raw_bytes_is_taken_as_it_is():
    part = XmlPart(DOC)
    part.replace(paragraphs(part)[2], b"<t:p>filled</t:p>")
    assert part.result() == DOC.replace(b"<t:p/>", b"<t:p>filled</t:p>")


def test_remove_takes_the_element_out_and_leaves_the_rest():
    part = XmlPart(DOC)
    part.remove(paragraphs(part)[2])
    assert part.result() == DOC.replace(b"<t:p/>", b"")


def test_insert_after_and_before_place_a_new_element_next_to_an_old_one():
    part = XmlPart(DOC)
    one, two, *_ = paragraphs(part)
    part.insert_after(one, part.make("t:p", text="after one"))
    part.insert_before(two, part.make("t:p", text="before two"))
    out = part.result()
    assert out.index(b"after one") < out.index(b"before two") < out.index(b"two <t:span>")
    assert out.count(b"<t:p") == DOC.count(b"<t:p") + 2


def test_several_inserts_at_one_place_keep_the_order_they_were_made_in():
    part = XmlPart(DOC)
    one = paragraphs(part)[0]
    for word in ("a", "b", "c"):
        part.insert_after(one, part.make("t:p", text=word))
    out = part.result()
    assert out.index(b">a<") < out.index(b">b<") < out.index(b">c<")


def test_insert_into_puts_a_child_last_or_first():
    part = XmlPart(DOC)
    body = next(el for el in part.elements() if el.tag == "{urn:o}body")
    part.insert_into(body, part.make("t:p", text="last"))
    part.insert_into(body, part.make("t:p", text="first"), at_start=True)
    out = part.result()
    assert out.index(b">first<") < out.index(b">one<") < out.index(b">last<") < out.index(b"</o:body>")


def test_insert_into_an_empty_element_opens_it():
    part = XmlPart(DOC)
    empty = paragraphs(part)[2]
    part.insert_into(empty, part.make("t:span", text="x"))
    assert part.result() == DOC.replace(b"<t:p/>", b"<t:p><t:span>x</t:span></t:p>")


def test_an_edit_next_to_a_replaced_element_does_not_collide_with_it():
    part = XmlPart(DOC)
    one = paragraphs(part)[0]
    part.replace(one, part.make("t:p", text="1"))
    part.insert_after(one, part.make("t:p", text="1b"))
    part.insert_before(one, part.make("t:p", text="0"))
    out = part.result()
    assert out.index(b">0<") < out.index(b">1<") < out.index(b">1b<")


def test_two_edits_that_overlap_are_refused():
    part = XmlPart(DOC)
    body = next(el for el in part.elements() if el.tag == "{urn:o}body")
    part.replace(body, b"<o:body/>")
    part.remove(paragraphs(part)[0])  # inside the body that is being replaced
    with pytest.raises(OdfError, match="overlap"):
        part.result()


def test_only_an_element_of_this_part_can_be_edited():
    part = XmlPart(DOC)
    other = XmlPart(DOC)
    with pytest.raises(OdfError, match="not an element of this part"):
        part.remove(paragraphs(other)[0])


# -- new elements --------------------------------------------------------------------------------------------
def test_a_new_element_does_not_repeat_the_namespaces_the_part_already_declares():
    part = XmlPart(DOC)
    part.insert_after(paragraphs(part)[0], part.make("t:p", {"o:kind": "k"}, text="new"))
    assert b'<t:p o:kind="k">new</t:p>' in part.result()


def test_a_prefix_the_part_does_not_declare_is_declared_on_the_new_element():
    part = XmlPart(DOC)
    part.insert_after(paragraphs(part)[0], part.make("text:p", text="new"))
    out = part.result()
    assert b'<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">new</text:p>' in out


def test_a_new_element_can_hold_others_and_text_with_markup_characters():
    part = XmlPart(DOC)
    outer = part.make("t:p", text="a < b & ")
    outer.append(part.make("t:span", text="c"))
    part.insert_after(paragraphs(part)[0], outer)
    assert b"<t:p>a &lt; b &amp; <t:span>c</t:span></t:p>" in part.result()


def test_make_knows_the_attribute_prefixes_too():
    part = XmlPart(DOC)
    el = part.make("t:p", {"x:name": "v"})
    assert el.get("{urn:x}name") == "v"


# -- the file as it comes ------------------------------------------------------------------------------------
def test_a_file_that_is_not_xml_is_an_error_with_a_sentence():
    with pytest.raises(OdfError, match="not well-formed"):
        XmlPart(b"<a><b></a>")


def test_a_file_in_another_encoding_than_utf8_is_refused():
    with pytest.raises(OdfError, match="UTF-8"):
        XmlPart('<?xml version="1.0" encoding="UTF-16"?><a/>'.encode("utf-16"))


def test_a_byte_order_mark_is_kept_and_does_not_shift_the_spans():
    data = b"\xef\xbb\xbf" + DOC
    part = XmlPart(data)
    first = paragraphs(part)[0]
    part.replace(first, part.make("t:p", text="x"))
    assert part.result().startswith(b"\xef\xbb\xbf<?xml")
    assert b"<t:p>x</t:p>" in part.result()


def test_non_ascii_text_outside_the_edit_is_byte_identical():
    data = HEAD + '<o:doc xmlns:o="urn:o"><o:p>Größe — 日本語</o:p><o:p>x</o:p></o:doc>'.encode()
    part = XmlPart(data)
    second = [el for el in part.elements() if el.tag == "{urn:o}p"][1]
    part.replace(second, b"<o:p>y</o:p>")
    assert part.result() == data.replace(b"<o:p>x</o:p>", b"<o:p>y</o:p>")


def test_a_comment_and_a_cdata_section_do_not_confuse_the_element_order():
    data = HEAD + b'<o:doc xmlns:o="urn:o"><!-- <o:p>not one</o:p> --><o:p><![CDATA[a<b]]></o:p><o:p>two</o:p></o:doc>'
    part = XmlPart(data)
    paras = [el for el in part.elements() if el.tag == "{urn:o}p"]
    assert [data[slice(*part.span(p))] for p in paras] == [b"<o:p><![CDATA[a<b]]></o:p>", b"<o:p>two</o:p>"]


def test_several_elements_can_go_into_one_empty_parent_in_one_edit():
    part = XmlPart(b'<r xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><text:list/></r>')
    parent = part.elements()[1]
    part.insert_into(parent, part.make("text:p", text="a"), part.make("text:p", text="b"))
    assert part.result() == (
        b'<r xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        b"<text:list><text:p>a</text:p><text:p>b</text:p></text:list></r>"
    )


def test_several_elements_go_in_in_the_order_given_at_the_start_too():
    part = XmlPart(b'<r xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><text:p>x</text:p></r>')
    part.insert_into(part.root, part.make("text:p", text="a"), part.make("text:p", text="b"), at_start=True)
    assert part.result().endswith(b"<text:p>a</text:p><text:p>b</text:p><text:p>x</text:p></r>")


def test_an_empty_element_right_before_the_end_tag_of_its_parent_has_its_own_span():
    raw = b"<r><a><b/></a><c>x</c></r>"
    part = XmlPart(raw)
    spans = {e.tag: part.span(e) for e in part.elements()}
    assert raw[slice(*spans["b"])] == b"<b/>"
    assert raw[slice(*spans["a"])] == b"<a><b/></a>"
    part.remove(part.elements()[2])
    assert part.result() == b"<r><a></a><c>x</c></r>"


# -- set_attributes: change a start tag and nothing else (D412) -----------------------------------------------------
class TestSetAttributes:
    SOURCE = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<root xmlns:a="{NS["draw"]}" xmlns:s="{NS["svg"]}">'
        '<a:frame s:x=\'1cm\'  s:y="2cm" a:name="A &amp; B">text &apos;kept&apos;</a:frame>'
        '<a:frame s:x="3cm"/></root>'
    ).encode()

    def edited(self, which: int, values: dict[str, str]) -> bytes:
        part = XmlPart(self.SOURCE)
        part.set_attributes(part.root[which], values)
        return part.result()

    def test_changes_the_value_and_leaves_the_rest_of_the_tag_and_the_part_alone(self):
        result = self.edited(0, {"svg:x": "9cm"})
        assert b'<a:frame s:x=\'9cm\'  s:y="2cm" a:name="A &amp; B">text &apos;kept&apos;</a:frame>' in result
        assert result.endswith(b'<a:frame s:x="3cm"/></root>')

    def test_uses_the_prefixes_the_file_chose(self):
        assert b's:y="7cm"' in self.edited(0, {"svg:y": "7cm"})

    def test_adds_an_attribute_the_tag_lacks(self):
        result = self.edited(0, {"svg:width": "5cm"})
        assert b"svg:width" not in result and b's:width="5cm"' in result
        assert etree.fromstring(result)[0].get(f"{{{NS['svg']}}}width") == "5cm"

    def test_works_on_an_empty_element(self):
        result = self.edited(1, {"svg:x": "4cm", "svg:y": "5cm"})
        element = etree.fromstring(result)[1]
        assert (element.get(f"{{{NS['svg']}}}x"), element.get(f"{{{NS['svg']}}}y")) == ("4cm", "5cm")
        assert result.endswith(b"/></root>")

    def test_escapes_the_value(self):
        result = self.edited(0, {"draw:name": 'A "quoted" <b> & c'})
        assert etree.fromstring(result)[0].get(f"{{{NS['draw']}}}name") == 'A "quoted" <b> & c'

    def test_can_be_combined_with_an_edit_inside_the_element(self):
        part = XmlPart(self.SOURCE)
        part.set_attributes(part.root[0], {"svg:x": "9cm"})
        part.insert_into(part.root[0], b"<a:inner/>")
        assert b"<a:inner/></a:frame>" in part.result() and b"s:x='9cm'" in part.result()

    def test_a_namespace_the_file_does_not_declare_is_an_error(self):
        part = XmlPart(b'<root xmlns:a="x"><a:e/></root>')
        with pytest.raises(OdfError, match="namespace"):
            part.set_attributes(part.root[0], {"svg:x": "1cm"})
