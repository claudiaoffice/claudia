"""What a pivot table is: a definition, kept apart from the cells it fills (E6.30, D620).

A :class:`PivotDefinition` says which table or range to summarise (``source``, a name, D600), which field goes down
the ``rows``, which across the ``columns``, which fields are ``filters``, and which ``values`` are added up and how.
Nothing in it knows where the result is shown or how it is drawn: :func:`~claudia_computes.compute_pivot` makes a
query of it and the query's answer into a grid (D621).

This version takes at most one row field and one column field; the definition is shaped for more (they are tuples),
and a later version lifts the limit without changing anything stored. ``total_row`` and ``total_column`` are
Excel's "Grand totals for rows / for columns".

A definition is plain data: :meth:`PivotDefinition.to_data` is what the log stores and clients are sent,
:meth:`PivotDefinition.from_data` reads it back and names the first thing that is wrong, as
:class:`~claudia_computes.ChartSpec` does for charts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from claudia_core import N_, Refusal

from .values import Value

#: The version of this definition's own data format (mirrors ``charts.FORMAT``).
FORMAT = 1
#: What this version of the engine can put in a pivot (D620): the limit is the layout's, not the definition's.
MAX_ROW_FIELDS = 1
MAX_COLUMN_FIELDS = 1

_KEYS = {"format", "source", "rows", "columns", "values", "filters", "total_row", "total_column"}
_VALUE_KEYS = {"field", "aggregation", "name"}
_FILTER_KEYS = {"field", "keep"}


class PivotError(Refusal):
    """A pivot that is not right, or cannot be made; the message says what is wrong in words."""


class Aggregation(StrEnum):
    """How the values of one field are put together: Excel's "Summarize values by" (the five that SQLite has)."""

    SUM = "sum"
    COUNT = "count"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"

    @property
    def sql_function(self) -> str:
        """The SQL aggregate that does it."""
        return _FUNCTIONS[self]


_FUNCTIONS = {
    Aggregation.SUM: "SUM",
    Aggregation.COUNT: "COUNT",
    Aggregation.AVERAGE: "AVG",
    Aggregation.MIN: "MIN",
    Aggregation.MAX: "MAX",
}


@dataclass(frozen=True, slots=True)
class PivotLabels:
    """The words a pivot puts in its own cells, so that a client can give them in the person's language (the
    server's pivot is the same in every language; its words are not). ``sum_of`` and its kind are made into a value
    field's title with ``{field}`` standing for the field's name."""

    total: str = "Total"
    blank: str = "(blank)"
    row_header: str = "Rows"
    sum_of: str = "Sum of {field}"
    count_of: str = "Count of {field}"
    average_of: str = "Average of {field}"
    min_of: str = "Min of {field}"
    max_of: str = "Max of {field}"

    def title(self, aggregation: Aggregation, field: str) -> str:
        """The title a value field has when it has no name of its own: ``Sum of Amount``."""
        template = {
            Aggregation.SUM: self.sum_of,
            Aggregation.COUNT: self.count_of,
            Aggregation.AVERAGE: self.average_of,
            Aggregation.MIN: self.min_of,
            Aggregation.MAX: self.max_of,
        }[aggregation]
        return template.format(field=field)

    def to_data(self) -> dict[str, str]:
        """The plain-data form (every word, so that a pivot reads the same wherever it is opened)."""
        return {name: getattr(self, name) for name in _LABEL_KEYS}

    @classmethod
    def from_data(cls, data: object) -> PivotLabels:
        """Read the plain-data form; words that are not given are the English ones. Raises :class:`PivotError`."""
        if not isinstance(data, dict):
            raise PivotError("labels: one JSON object of words")
        _only(data, set(_LABEL_KEYS), "the labels")
        if not all(isinstance(word, str) for word in data.values()):
            raise PivotError("labels: every word is text")
        return cls(**data)


_LABEL_KEYS = ("total", "blank", "row_header", "sum_of", "count_of", "average_of", "min_of", "max_of")


#: The English words; a client that speaks another language passes its own.
DEFAULT_LABELS = PivotLabels()


def _is_member(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float))


@dataclass(frozen=True, slots=True)
class ValueField:
    """One field to summarise, how, and (when it is not to be called ``Sum of Amount``) under what name."""

    field: str
    aggregation: Aggregation = Aggregation.SUM
    name: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.field, str) or not self.field.strip():
            raise PivotError("a value field names a field of the source")
        if not isinstance(self.name, str) or not self.name.isprintable():
            raise PivotError("name: must be a line of text")


@dataclass(frozen=True, slots=True)
class PivotFilter:
    """A field that cuts the source down before anything is added up. ``keep`` lists the members that stay, ``None``
    keeps them all (Excel's "(All)"): the field is in the filter area, ready to be narrowed."""

    field: str
    keep: tuple[Value, ...] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.field, str) or not self.field.strip():
            raise PivotError("a filter names a field of the source")
        if self.keep is not None and (not self.keep or not all(_is_member(member) for member in self.keep)):
            raise PivotError("keep: the members to keep, at least one, each a number, text or nothing")


@dataclass(frozen=True, slots=True)
class PivotDefinition:
    """Everything a pivot is made from. See the module's text; every field name is a column of ``source``, found
    without regard to case."""

    source: str
    rows: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    values: tuple[ValueField, ...] = ()
    filters: tuple[PivotFilter, ...] = ()
    total_row: bool = True
    total_column: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise PivotError("source: must be the name of a table or range")
        if len(self.rows) > MAX_ROW_FIELDS:
            raise PivotError(N_("rows: at most one row field in this version"))
        if len(self.columns) > MAX_COLUMN_FIELDS:
            raise PivotError(N_("columns: at most one column field in this version"))
        seen: dict[str, str] = {}
        for field in (*self.rows, *self.columns, *(each.field for each in self.filters)):
            if field.casefold() in seen:
                raise PivotError(
                    N_("“{field}” is in two places: a field is in rows, columns or filters, not in more"),
                    field=seen[field.casefold()],
                )
            seen.setdefault(field.casefold(), field)

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {
            "format": FORMAT,
            "source": self.source,
            "rows": list(self.rows),
            "columns": list(self.columns),
            "values": [
                {"field": each.field, "aggregation": each.aggregation.value, "name": each.name} for each in self.values
            ],
            "filters": [
                {"field": each.field, "keep": None if each.keep is None else list(each.keep)} for each in self.filters
            ],
            "total_row": self.total_row,
            "total_column": self.total_column,
        }

    @classmethod
    def from_data(cls, data: object) -> PivotDefinition:
        """Read the plain-data form; raises :class:`PivotError` naming the first thing that is wrong. Whether the
        fields exist in the source is :func:`~claudia_computes.compute_pivot`'s business: only it sees the source."""
        if not isinstance(data, dict):
            raise PivotError("a pivot definition is one JSON object")
        _only(data, _KEYS, "a pivot")
        if "source" not in data:
            raise PivotError("missing 'source'")
        if data.get("format") != FORMAT or isinstance(data.get("format"), bool):
            raise PivotError(f"format: this version reads format {FORMAT}, the data says {data.get('format')!r}")
        return cls(
            source=data["source"],
            rows=_names(data.get("rows", []), "rows"),
            columns=_names(data.get("columns", []), "columns"),
            values=tuple(_value_field(each) for each in _items(data.get("values", []), "values")),
            filters=tuple(_filter(each) for each in _items(data.get("filters", []), "filters")),
            total_row=_flag(data.get("total_row", True), "total_row"),
            total_column=_flag(data.get("total_column", True), "total_column"),
        )


def _only(data: dict, keys: set[str], what: str) -> None:
    unknown = sorted(str(key) for key in set(data) - keys)
    if unknown:
        raise PivotError(f"unknown key {unknown[0]!r}: {what} has {', '.join(sorted(keys))}")


def _items(value: object, name: str) -> list:
    if not isinstance(value, list):
        raise PivotError(f"{name}: must be a list")
    return value


def _names(value: object, name: str) -> tuple[str, ...]:
    items = _items(value, name)
    if not all(isinstance(item, str) and item.strip() for item in items):
        raise PivotError(f"{name}: a list of field names")
    return tuple(items)


def _flag(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise PivotError(f"{name}: must be true or false")
    return value


def _value_field(data: object) -> ValueField:
    if not isinstance(data, dict):
        raise PivotError("values: each is one JSON object")
    _only(data, _VALUE_KEYS, "a value field")
    kind = data.get("aggregation", Aggregation.SUM.value)
    try:
        aggregation = Aggregation(kind)
    except ValueError:
        options = ", ".join(each.value for each in Aggregation)
        raise PivotError(f"aggregation: one of {options}, not {kind!r}") from None
    return ValueField(data.get("field"), aggregation, data.get("name", ""))  # type: ignore[arg-type]


def _filter(data: object) -> PivotFilter:
    if not isinstance(data, dict):
        raise PivotError("filters: each is one JSON object")
    _only(data, _FILTER_KEYS, "a filter")
    keep = data.get("keep")
    if keep is not None and not isinstance(keep, list):
        raise PivotError("keep: a list of members, or null to keep them all")
    return PivotFilter(data.get("field"), None if keep is None else tuple(keep))  # type: ignore[arg-type]
