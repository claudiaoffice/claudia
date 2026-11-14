"""Functions that give several cells: SEQUENCE, TRANSPOSE, SORT, FILTER, UNIQUE ..., matrix algebra and regression.

A function here returns a ``Matrix``: a rectangle of values that spills into the cells below and to the right of its
formula (``claudia_computes.spill``). An empty cell inside a result is 0, as in Excel. Where the result is shorter in
one direction than another part of it (``VSTACK`` of ranges of different widths) the gap is ``#N/A``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from fractions import Fraction

from ...limits import MAX_COLS, MAX_ROWS
from ...spill import Matrix
from ...values import NA, NUM, REF, VALUE, ErrorValue, Value
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .aggregate import ordered_numbers
from .catalog import builtin
from .ordering import group, identity, order_key

Rows = list[list[Value]]
N_A = ErrorValue(NA)


def rows_of(area: Range) -> Rows:
    """The values of a range as rows (an empty cell is ``None``; an error is kept as it is)."""
    return [list(row) for row in area.dense()]


def matrix(rows: Sequence[Sequence[Value]]) -> Matrix:
    """The rows as a result. An empty cell becomes 0; nothing at all is ``#N/A`` (there is nothing to spill)."""
    if not rows or not rows[0]:
        raise FunctionError(NA, "nothing matched")
    if len(rows) > MAX_ROWS or len(rows[0]) > MAX_COLS:
        raise FunctionError(VALUE, "this result does not fit on a sheet")
    return Matrix(tuple(tuple(0 if value is None else value for value in row) for row in rows))


def transposed(rows: Rows) -> Rows:
    return [list(column) for column in zip(*rows, strict=True)]


def numbers_matrix(area: Range, what: str = "this") -> list[list[float]]:
    """A range that must hold numbers only, as rows of floats (``#VALUE!`` for text or an empty cell)."""
    out = []
    for row in area.dense():
        line = []
        for value in row:
            if value.__class__ is ErrorValue:
                raise value.raised()
            if value.__class__ not in (int, float):
                raise FunctionError(VALUE, f"{what} must hold numbers only")
            line.append(value)
        out.append(line)
    return out


# -- building and reshaping --------------------------------------------------------------------------------------------
@builtin
class SEQUENCE(UserFunction):
    description = "A grid of numbers that count up from a start by a step: rows, columns, start (1), step (1)."
    examples = (Example("=SUM(SEQUENCE(4))", 10), Example("=INDEX(SEQUENCE(2, 2, 10, 5), 2, 1)", 20))

    def call(self, rows: int, columns: int | None = None, start: float | None = None, step: float | None = None):
        cols = 1 if columns is None else columns
        first, by = (1 if start is None else start), (1 if step is None else step)
        if rows < 1 or cols < 1:
            raise FunctionError(VALUE, "a sequence needs at least one row and one column")
        if rows > MAX_ROWS or cols > MAX_COLS:
            raise FunctionError(VALUE, "this does not fit on a sheet")
        whole = all(float(n).is_integer() for n in (first, by))
        make = (lambda v: int(v)) if whole else (lambda v: v)
        return Matrix(tuple(tuple(make(first + (i * cols + j) * by) for j in range(cols)) for i in range(rows)))


@builtin
class TRANSPOSE(UserFunction):
    description = "Swaps the rows and columns of a range."
    examples = (Example("=INDEX(TRANSPOSE(A1:C1), 3, 1)", 30, {"A1": 10, "B1": 20, "C1": 30}),)

    def call(self, array: Range):
        return matrix(transposed(rows_of(array)))


def _stack(arrays: tuple[Range, ...], *, down: bool) -> Matrix:
    blocks = [rows_of(a) for a in arrays]
    if down:
        width = max(len(block[0]) for block in blocks)
        out: Rows = []
        for block in blocks:
            out.extend(line + [N_A] * (width - len(line)) for line in block)
        return matrix(out)
    height = max(len(block) for block in blocks)
    out = [[] for _ in range(height)]
    for block in blocks:
        width = len(block[0])
        for i in range(height):
            out[i].extend(block[i] if i < len(block) else [N_A] * width)
    return matrix(out)


@builtin
class VSTACK(UserFunction):
    description = "Puts ranges one below the other; the narrower ones are filled up with #N/A."
    examples = (Example("=ROWS(VSTACK(A1:B2, A1:B1))", 3, {"A1": 1, "B1": 2, "A2": 3, "B2": 4}),)

    def call(self, *arrays: Range):
        return _stack(arrays, down=True)


@builtin
class HSTACK(UserFunction):
    description = "Puts ranges side by side; the shorter ones are filled up with #N/A."
    examples = (Example("=COLUMNS(HSTACK(A1:B2, A1:A2))", 3, {"A1": 1, "B1": 2, "A2": 3, "B2": 4}),)

    def call(self, *arrays: Range):
        return _stack(arrays, down=False)


# -- sorting, filtering, unique values -------------------------------------------------------------------------------
def _order(order: int | None, what: str = "the sort order") -> bool:
    """True for descending. ``order`` is 1 (up) or -1 (down); left out it is up."""
    if order is None:
        return False
    if order not in (1, -1):
        raise FunctionError(VALUE, f"{what} is 1 (ascending) or -1 (descending)")
    return order == -1


def _sorted_rows(rows: Rows, keys: list[tuple[list[Value], bool]]) -> Rows:
    """``rows`` ordered by the key columns (values, descending), the first key first; equal rows keep their order."""
    positions = list(range(len(rows)))
    for values, descending in reversed(keys):
        positions.sort(key=lambda i: order_key(values[i], descending), reverse=descending)
    return [rows[i] for i in positions]


@builtin
class SORT(UserFunction):
    description = (
        "Sorts the rows of a range by a column (the first unless given), up or down; with by_col TRUE it sorts "
        "the columns by a row."
    )
    examples = (Example("=INDEX(SORT(A1:A3), 1)", 1, {"A1": 3, "A2": 1, "A3": 2}),)

    def call(self, array: Range, sort_index: int | None = None, sort_order: int | None = None, by_col: bool = False):
        rows = rows_of(array)
        if by_col:
            rows = transposed(rows)
        index = 1 if sort_index is None else sort_index
        if not 1 <= index <= len(rows[0]):
            raise FunctionError(VALUE, f"there is no {'row' if by_col else 'column'} {index} to sort by")
        descending = _order(sort_order)
        ordered = _sorted_rows(rows, [([line[index - 1] for line in rows], descending)])
        return matrix(transposed(ordered) if by_col else ordered)


@builtin
class SORTBY(UserFunction):
    description = "Sorts a range by the values of other ranges of the same height: by_array, order, by_array, order ..."
    examples = (Example("=INDEX(SORTBY(A1:A3, B1:B3), 1)", "y", {"A1": "x", "A2": "y", "A3": "z", "B1": 3, "B2": 1, "B3": 2}),)

    def call(self, array: Range, by_array: Range, *more: Range):
        rows = rows_of(array)
        by_row = array.n_rows == 1 and array.n_cols > 1
        if by_row:
            rows = transposed(rows)
        arguments = [by_array, *more]  # key, order, key, order ...: the last order may be left out
        keys: list[tuple[list[Value], bool]] = []
        for index in range(0, len(arguments), 2):
            values = [v for line in rows_of(arguments[index]) for v in line]
            if len(values) != len(rows):
                raise FunctionError(VALUE, "each range to sort by must be as long as the range sorted")
            order = arguments[index + 1].at(0, 0) if index + 1 < len(arguments) else None
            keys.append((values, _order(order)))
        ordered = _sorted_rows(rows, keys)
        return matrix(transposed(ordered) if by_row else ordered)


@builtin
class UNIQUE(UserFunction):
    description = (
        "The different rows of a range in order of first appearance (columns with by_col TRUE); with exactly_once "
        "TRUE only those that occur once."
    )
    examples = (Example("=ROWS(UNIQUE(A1:A4))", 2, {"A1": 1, "A2": 2, "A3": 1, "A4": 2}),)

    def call(self, array: Range, by_col: bool = False, exactly_once: bool = False):
        rows = rows_of(array)
        if by_col:
            rows = transposed(rows)
        counts: dict[tuple, int] = {}
        first: dict[tuple, int] = {}
        for i, line in enumerate(rows):
            key = tuple(identity(v) for v in line)
            counts[key] = counts.get(key, 0) + 1
            first.setdefault(key, i)
        kept = [rows[i] for key, i in first.items() if not exactly_once or counts[key] == 1]
        if not kept:
            raise FunctionError(NA, "no value occurs exactly once")
        return matrix(transposed(kept) if by_col else kept)


def _condition(value: Value) -> bool:
    if value.__class__ is ErrorValue:
        raise value.raised()
    if value is None:
        return False
    if value.__class__ is bool:
        return value
    if isinstance(value, (int, float)):
        return value != 0
    raise FunctionError(VALUE, "a condition must be TRUE or FALSE, or a number")


@builtin
class FILTER(UserFunction):
    description = (
        "The rows of a range for which the condition range holds (a column of TRUE/FALSE or numbers; a row filters "
        "the columns). If nothing matches, the third argument, else #N/A."
    )
    examples = (Example("=SUM(FILTER(A1:A3, B1:B3>1))", 5, {"A1": 1, "A2": 2, "A3": 3, "B1": 1, "B2": 2, "B3": 3}),)

    def call(self, array: Range, include: Range, if_empty=None):
        conditions = [v for row in rows_of(include) for v in row]
        rows = rows_of(array)
        if include.n_cols == 1 and include.n_rows == array.n_rows:
            kept = [line for line, flag in zip(rows, conditions, strict=True) if _condition(flag)]
        elif include.n_rows == 1 and include.n_cols == array.n_cols:
            wanted = [j for j, flag in enumerate(conditions) if _condition(flag)]
            kept = [[line[j] for j in wanted] for line in rows] if wanted else []
        else:
            raise FunctionError(VALUE, "the condition must be one column as tall as the range, or one row as wide")
        if not kept or not kept[0]:
            if if_empty is None:
                raise FunctionError(NA, "nothing matched")
            return if_empty
        return matrix(kept)


# -- matrix algebra ---------------------------------------------------------------------------------------------------
def _exact(rows: list[list[float]]) -> bool:
    return all(v.__class__ is int for line in rows for v in line)


def _square(rows: list[list[float]]) -> int:
    if len(rows) != len(rows[0]):
        raise FunctionError(VALUE, "this needs a square matrix")
    return len(rows)


def _determinant(rows: list[list[float]]) -> float:
    n = _square(rows)
    exact = _exact(rows)
    work = [[Fraction(v) if exact else float(v) for v in line] for line in rows]
    det = Fraction(1) if exact else 1.0
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(work[r][col]))
        if work[pivot][col] == 0:
            return 0
        if pivot != col:
            work[col], work[pivot] = work[pivot], work[col]
            det = -det
        det *= work[col][col]
        for r in range(col + 1, n):
            factor = work[r][col] / work[col][col]
            for c in range(col, n):
                work[r][c] -= factor * work[col][c]
    return int(det) if exact and det.denominator == 1 else float(det)


def _inverse(rows: list[list[float]]) -> list[list[float]]:
    n = _square(rows)
    exact = _exact(rows)
    one, zero = (Fraction(1), Fraction(0)) if exact else (1.0, 0.0)
    work = [[(Fraction(v) if exact else float(v)) for v in line] + [one if i == j else zero for j in range(n)] for i, line in enumerate(rows)]
    scale = max(abs(v) for line in rows for v in line) or 1
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(work[r][col]))
        if abs(work[pivot][col]) <= 1e-13 * scale:
            raise FunctionError(NUM, "the matrix is singular: it has no inverse")
        work[col], work[pivot] = work[pivot], work[col]
        head = work[col][col]
        work[col] = [v / head for v in work[col]]
        for r in range(n):
            if r != col and work[r][col] != 0:
                factor = work[r][col]
                work[r] = [a - factor * b for a, b in zip(work[r], work[col], strict=True)]
    return [[float(v) for v in line[n:]] for line in work]


@builtin
class MDETERM(UserFunction):
    description = "The determinant of a square matrix of numbers."
    examples = (Example("=MDETERM(A1:B2)", -2, {"A1": 1, "B1": 2, "A2": 3, "B2": 4}),)

    def call(self, array: Range):
        return _determinant(numbers_matrix(array))


@builtin
class MINVERSE(UserFunction):
    description = "The inverse of a square matrix of numbers (#NUM! when it has none)."
    examples = (Example("=INDEX(MINVERSE(A1:B2), 1, 1)", -2, {"A1": 1, "B1": 2, "A2": 3, "B2": 4}),)

    def call(self, array: Range):
        return matrix(_inverse(numbers_matrix(array)))


@builtin
class MMULT(UserFunction):
    description = "The product of two matrices: the first must have as many columns as the second has rows."
    examples = (Example("=INDEX(MMULT(A1:B1, A2:B3), 1, 1)", 13, {"A1": 1, "B1": 2, "A2": 3, "B2": 4, "A3": 5, "B3": 6}),)

    def call(self, first: Range, second: Range):
        a, b = numbers_matrix(first), numbers_matrix(second)
        if len(a[0]) != len(b):
            raise FunctionError(VALUE, "the first matrix needs as many columns as the second has rows")
        columns = transposed(b)
        exact = _exact(a) and _exact(b)
        return matrix(
            [[sum(x * y for x, y in zip(line, col, strict=True)) if exact else math.fsum(x * y for x, y in zip(line, col, strict=True)) for col in columns] for line in a]
        )


@builtin
class MUNIT(UserFunction):
    description = "The identity matrix of a size: 1 on the diagonal, 0 elsewhere."
    examples = (Example("=SUM(MUNIT(3))", 3),)

    def call(self, size: int):
        if size < 1 or size > min(MAX_ROWS, MAX_COLS):
            raise FunctionError(VALUE, "the size must be 1 or more")
        return Matrix(tuple(tuple(1 if i == j else 0 for j in range(size)) for i in range(size)))


# -- counting into bins, modes --------------------------------------------------------------------------------------
@builtin
class FREQUENCY(UserFunction):
    description = "How many of the data fall into each bin: up to the first limit, above it up to the next ... and above the last."
    examples = (Example("=INDEX(FREQUENCY(A1:A4, B1:B2), 1)", 2, {"A1": 1, "A2": 2, "A3": 5, "A4": 9, "B1": 3, "B2": 6}),)

    def call(self, data: Range, bins: Range):
        values = data.numbers(strict=False)
        limits = sorted(bins.numbers(strict=False))
        counts = [0] * (len(limits) + 1)
        for v in values:
            slot = next((i for i, limit in enumerate(limits) if v <= limit), len(limits))
            counts[slot] += 1
        return Matrix(tuple((c,) for c in counts))


@builtin
class MODE_MULT(UserFunction):
    name = "MODE.MULT"
    description = "The numbers that occur most often, in order of first appearance, as a column (#N/A if none repeats)."
    examples = (Example("=SUM(MODE.MULT(A1:A5))", 5, {"A1": 1, "A2": 2, "A3": 3, "A4": 2, "A5": 3}),)

    def call(self, *values: Range):
        found = [n for area in values for n in ordered_numbers(area)]
        counts: dict[float, int] = {}
        for n in found:
            counts[n] = counts.get(n, 0) + 1
        top = max(counts.values(), default=0)
        if top < 2:
            raise FunctionError(NA, "no number occurs more than once")
        return Matrix(tuple((n,) for n, c in counts.items() if c == top))


# -- regression -----------------------------------------------------------------------------------------------------
class Fit:
    """A least-squares fit of y on the columns of x (with a constant unless ``constant`` is false)."""

    def __init__(self, ys: list[float], xs: list[list[float]], constant: bool):
        n, k = len(ys), len(xs[0])
        p = k + (1 if constant else 0)
        if n < p:
            raise FunctionError("#DIV/0!", "there are fewer points than numbers to fit")
        design = [([1.0] if constant else []) + list(row) for row in xs]
        coefficients, r_inverse = _least_squares(design, ys)
        self.constant, self.n, self.k, self.p = constant, n, k, p
        self.beta = coefficients
        fitted = [sum(b * v for b, v in zip(coefficients, row, strict=True)) for row in design]
        self.ss_resid = math.fsum((y - f) ** 2 for y, f in zip(ys, fitted, strict=True))
        centre = math.fsum(ys) / n if constant else 0.0
        self.ss_total = math.fsum((y - centre) ** 2 for y in ys)
        self.ss_reg = self.ss_total - self.ss_resid
        self.df = n - p
        # (R'R)^-1 = R^-1 R^-T: its diagonal gives the variances of the coefficients
        self.diagonal = [math.fsum(v * v for v in line) for line in r_inverse]

    def predict(self, row: Sequence[float]) -> float:
        values = ([1.0] if self.constant else []) + list(row)
        return math.fsum(b * v for b, v in zip(self.beta, values, strict=True))

    @property
    def slopes(self) -> list[float]:
        return self.beta[1:] if self.constant else self.beta

    @property
    def intercept(self) -> float:
        return self.beta[0] if self.constant else 0.0

    def statistics(self) -> tuple[list[float | ErrorValue], list[float | ErrorValue], list[float | ErrorValue], list[float | ErrorValue], list[float | ErrorValue]]:
        """The rows LINEST shows (coefficients, standard errors, r2 and standard error of y, F and df, sums of
        squares), each as long as the coefficients, in LINEST's reverse order."""
        sey = math.sqrt(self.ss_resid / self.df) if self.df > 0 else 0.0
        errors = [sey * math.sqrt(d) for d in self.diagonal]
        ses = errors[1:] if self.constant else errors
        se_b: float | ErrorValue = errors[0] if self.constant else ErrorValue(NA)
        r2 = self.ss_reg / self.ss_total if self.ss_total else 1.0
        f_value: float | ErrorValue = (
            (self.ss_reg / self.k) / (self.ss_resid / self.df) if self.df > 0 and self.ss_resid > 0 else ErrorValue(NUM)
        )
        coefficients = [*reversed(self.slopes), self.intercept]
        standard = [*reversed(ses), se_b]
        width = len(coefficients)
        pad = [ErrorValue(NA)] * (width - 2)
        return (
            coefficients,
            standard,
            [r2, sey, *pad],
            [f_value, self.df, *pad],
            [self.ss_reg, self.ss_resid, *pad],
        )


def _least_squares(design: list[list[float]], ys: list[float]) -> tuple[list[float], list[list[float]]]:
    """Solve ``design @ beta = ys`` by Householder QR (stable for the nearly dependent columns of dates and years);
    gives ``beta`` and the inverse of the triangular factor R."""
    n, p = len(design), len(design[0])
    a = [row[:] for row in design]
    b = list(ys)
    for j in range(p):
        norm = math.sqrt(math.fsum(a[i][j] ** 2 for i in range(j, n)))
        if norm == 0:
            raise FunctionError(NUM, "the x values depend on each other: no single line fits")
        alpha = -math.copysign(norm, a[j][j])
        v = [a[i][j] for i in range(j, n)]
        v[0] -= alpha
        vnorm2 = math.fsum(x * x for x in v)
        if vnorm2 == 0:
            continue
        for c in range(j, p):
            s = 2 * math.fsum(v[i - j] * a[i][c] for i in range(j, n)) / vnorm2
            for i in range(j, n):
                a[i][c] -= s * v[i - j]
        s = 2 * math.fsum(v[i - j] * b[i] for i in range(j, n)) / vnorm2
        for i in range(j, n):
            b[i] -= s * v[i - j]
    scale = max(abs(a[i][i]) for i in range(p))
    if any(abs(a[i][i]) <= 1e-12 * scale for i in range(p)):
        raise FunctionError(NUM, "the x values depend on each other: no single line fits")
    beta = [0.0] * p
    for i in range(p - 1, -1, -1):
        beta[i] = (b[i] - math.fsum(a[i][c] * beta[c] for c in range(i + 1, p))) / a[i][i]
    inverse = [[0.0] * p for _ in range(p)]
    for col in range(p):
        for i in range(p - 1, -1, -1):
            rhs = (1.0 if i == col else 0.0) - math.fsum(a[i][c] * inverse[c][col] for c in range(i + 1, p))
            inverse[i][col] = rhs / a[i][i]
    return beta, inverse


def _data(known_y: Range, known_x: Range | None, *, logs: bool) -> tuple[list[float], list[list[float]], bool]:
    """The y values, the x values as one row per point, and whether y runs along a row."""
    y_rows = numbers_matrix(known_y, "the known y values")
    by_row = known_y.n_rows == 1 and known_y.n_cols > 1
    ys = y_rows[0] if by_row else [line[0] for line in y_rows] if known_y.n_cols == 1 else None
    if ys is None:
        raise FunctionError(REF, "the known y values must be one row or one column")
    if logs:
        if any(y <= 0 for y in ys):
            raise FunctionError(NUM, "an exponential fit needs y values above 0")
        ys = [math.log(y) for y in ys]
    if known_x is None:
        return ys, [[float(i + 1)] for i in range(len(ys))], by_row
    x_rows = numbers_matrix(known_x, "the known x values")
    points = transposed(x_rows) if by_row else x_rows
    if len(points) != len(ys):
        raise FunctionError(REF, "there must be one x value (or row of them) for every y value")
    return ys, points, by_row


def _new_points(new_x: Range, by_row: bool, k: int) -> tuple[list[list[float]], tuple[int, int] | None]:
    """The points to predict at, and the shape of the result (``None``: one value per point as a column or row)."""
    grid = numbers_matrix(new_x, "the new x values")
    if k == 1:
        return [[v] for line in grid for v in line], (len(grid), len(grid[0]))
    points = transposed(grid) if by_row else grid
    if len(points[0]) != k:
        raise FunctionError(REF, "the new x values need as many variables as the known x values")
    return points, None


def _shaped(values: list[float], shape: tuple[int, int] | None, by_row: bool) -> Matrix:
    if shape is not None:
        width = shape[1]
        return Matrix(tuple(tuple(values[i * width : (i + 1) * width]) for i in range(shape[0])))
    return Matrix((tuple(values),)) if by_row else Matrix(tuple((v,) for v in values))


def _trend(known_y, known_x, new_x, constant, *, logs):
    ys, points, by_row = _data(known_y, known_x, logs=logs)
    fit = Fit(ys, points, constant)
    if new_x is None:
        known = known_x if known_x is not None else known_y
        grid = [[fit.predict(p)] for p in points]
        values = [row[0] for row in grid]
        shape = (known.n_rows, known.n_cols) if fit.k == 1 else None
        if fit.k == 1 and known_x is None:
            shape = (known_y.n_rows, known_y.n_cols)
        out = [math.exp(v) if logs else v for v in values]
        return _shaped(out, shape, by_row)
    new_points, shape = _new_points(new_x, by_row, fit.k)
    out = [fit.predict(p) for p in new_points]
    return _shaped([math.exp(v) if logs else v for v in out], shape, by_row)


@builtin
class TREND(UserFunction):
    description = "Values on the straight line that fits the known y and x values best, at the new x values (the known ones if left out)."
    examples = (Example("=TREND(A1:A3, B1:B3, 4)", 8, {"A1": 2, "A2": 4, "A3": 6, "B1": 1, "B2": 2, "B3": 3}),)

    def call(self, known_y: Range, known_x: Range | None = None, new_x: Range | None = None, const: bool = True):
        return _trend(known_y, known_x, new_x, const, logs=False)


@builtin
class GROWTH(UserFunction):
    description = "Values on the exponential curve y = b * m^x that fits the known y and x values best, at the new x values."
    examples = (Example("=ROUND(GROWTH(A1:A3, B1:B3, 4), 6)", 162, {"A1": 6, "A2": 18, "A3": 54, "B1": 1, "B2": 2, "B3": 3}),)

    def call(self, known_y: Range, known_x: Range | None = None, new_x: Range | None = None, const: bool = True):
        return _trend(known_y, known_x, new_x, const, logs=True)


def _linest(known_y, known_x, const, stats, *, logs):
    ys, points, _ = _data(known_y, known_x, logs=logs)
    fit = Fit(ys, points, const)
    rows = fit.statistics()
    if logs:
        rows = ([math.exp(c) for c in rows[0]], *rows[1:])
    return matrix(list(rows) if stats else [rows[0]])


@builtin
class LINEST(UserFunction):
    description = (
        "The straight line y = m1*x1 + ... + b through known y and x values, as a row: the coefficients in reverse "
        "order, then b; with stats TRUE also standard errors, r squared, F, degrees of freedom and sums of squares."
    )
    examples = (Example("=INDEX(LINEST(A1:A3, B1:B3), 1, 1)", 2, {"A1": 2, "A2": 4, "A3": 6, "B1": 1, "B2": 2, "B3": 3}),)

    def call(self, known_y: Range, known_x: Range | None = None, const: bool = True, stats: bool = False):
        return _linest(known_y, known_x, const, stats, logs=False)


@builtin
class LOGEST(UserFunction):
    description = "The exponential curve y = b * m1^x1 * ... through known y and x values, as a row (as LINEST gives them)."
    examples = (Example("=ROUND(INDEX(LOGEST(A1:A3, B1:B3), 1, 1), 6)", 3, {"A1": 6, "A2": 18, "A3": 54, "B1": 1, "B2": 2, "B3": 3}),)

    def call(self, known_y: Range, known_x: Range | None = None, const: bool = True, stats: bool = False):
        return _linest(known_y, known_x, const, stats, logs=True)
