"""A refusal keeps the English sentence and what it was made of, so that it can be said in another language (CODE-78,
D1510)."""

from __future__ import annotations

import pytest

from claudia_core import Refusal


def test_a_refusal_reads_as_its_english_sentence_filled_in() -> None:
    refusal = Refusal("There is already a sheet called “{name}”", name="Costs")
    assert str(refusal) == "There is already a sheet called “Costs”"


def test_a_refusal_keeps_its_template_and_parameters() -> None:
    refusal = Refusal("a holder has at most {limit} objects", limit=500)
    assert (refusal.template, refusal.params) == ("a holder has at most {limit} objects", {"limit": 500})


def test_a_refusal_without_parameters_is_its_template_untouched() -> None:
    assert str(Refusal("a table keeps at least one row {as is}")) == "a table keeps at least one row {as is}"


def test_a_refusal_is_caught_where_a_value_error_is() -> None:
    with pytest.raises(ValueError, match="a sheet needs a name"):
        raise Refusal("a sheet needs a name")
