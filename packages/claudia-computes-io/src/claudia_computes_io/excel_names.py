"""The names Excel writes in a file for the functions it added after 2007 (D340).

Excel stores ``IFS(...)`` as ``_xlfn.IFS(...)`` and ``SORT(...)`` as ``_xlfn._xlws.SORT(...)`` in an xlsx file, so that
an older Excel shows ``#NAME?`` instead of guessing. A formula read from a file drops these marks; a formula written
to a file gets them back, or Excel itself shows ``#NAME?`` for a function it knows. The list is Microsoft's (the
"future functions" of the file format), not the functions claudia has: a file may name any of them.
"""

from __future__ import annotations

from .extensions import rename_calls

_FUTURE_WORDS = """
    ACOT ACOTH AGGREGATE ANCHORARRAY ARABIC ARRAYTOTEXT BASE BETA.DIST BETA.INV BINOM.DIST BINOM.DIST.RANGE
    BINOM.INV BITAND BITLSHIFT BITOR BITRSHIFT BITXOR BYCOL BYROW CEILING.MATH CEILING.PRECISE CHISQ.DIST
    CHISQ.DIST.RT CHISQ.INV CHISQ.INV.RT CHISQ.TEST CHOOSECOLS CHOOSEROWS COMBINA CONCAT CONFIDENCE.NORM
    CONFIDENCE.T COT COTH COVARIANCE.P COVARIANCE.S CSC CSCH DAYS DECIMAL DROP ECMA.CEILING ERF.PRECISE ERFC.PRECISE
    EXPAND EXPON.DIST F.DIST F.DIST.RT F.INV F.INV.RT F.TEST FIELDVALUE FILTERXML FLOOR.MATH FLOOR.PRECISE
    FORECAST.ETS FORECAST.ETS.CONFINT FORECAST.ETS.SEASONALITY FORECAST.ETS.STAT FORECAST.LINEAR FORMULATEXT GAMMA
    GAMMA.DIST GAMMA.INV GAMMALN.PRECISE GAUSS GROUPBY HSTACK HYPGEOM.DIST IFNA IFS IMAGE IMCOSH IMCOT IMCSC IMCSCH
    IMSEC IMSECH IMSINH IMTAN ISFORMULA ISOCEILING ISOMITTED ISOWEEKNUM LAMBDA LET LOGNORM.DIST LOGNORM.INV
    MAKEARRAY MAP MAXIFS MINIFS MODE.MULT MODE.SNGL MUNIT NEGBINOM.DIST NETWORKDAYS.INTL NORM.DIST NORM.INV
    NORM.S.DIST NORM.S.INV NUMBERVALUE PDURATION PERCENTILE.EXC PERCENTILE.INC PERCENTOF PERCENTRANK.EXC
    PERCENTRANK.INC PERMUTATIONA PHI PIVOTBY POISSON.DIST QUARTILE.EXC QUARTILE.INC RANDARRAY RANK.AVG RANK.EQ
    REDUCE REGEXEXTRACT REGEXREPLACE REGEXTEST RRI SCAN SEC SECH SEQUENCE SHEET SHEETS SINGLE SKEW.P SORTBY STDEV.P
    STDEV.S SWITCH T.DIST T.DIST.2T T.DIST.RT T.INV T.INV.2T T.TEST TAKE TEXTAFTER TEXTBEFORE TEXTJOIN TEXTSPLIT
    TOCOL TOROW TRIMRANGE UNICHAR UNICODE UNIQUE VALUETOTEXT VAR.P VAR.S VSTACK WEBSERVICE WEIBULL.DIST WORKDAY.INTL
    WRAPCOLS WRAPROWS XLOOKUP XMATCH XOR Z.TEST
"""
#: Functions Excel writes as ``_xlfn.NAME``.
FUTURE_FUNCTIONS = frozenset(_FUTURE_WORDS.split())
#: Functions Excel writes as ``_xlfn._xlws.NAME``.
WORKSHEET_FUNCTIONS = frozenset({"FILTER", "SORT"})
_MARKS = ("_XLFN._XLWS.", "_XLFN.", "_XLWS.")


def _unmarked(name: str) -> str:
    upper = name.upper()
    for mark in _MARKS:
        if upper.startswith(mark):
            return name[len(mark) :]
    return name


def _marked(name: str) -> str:
    upper = name.upper()
    if upper in WORKSHEET_FUNCTIONS:
        return "_xlfn._xlws." + name
    return "_xlfn." + name if upper in FUTURE_FUNCTIONS else name


def without_marks(text: str) -> str:
    """The formula ``text`` from a file with Excel's ``_xlfn.`` and ``_xlws.`` marks taken off its function names."""
    return rename_calls(text, _unmarked) if "_XL" in text.upper() else text


def with_marks(text: str) -> str:
    """The formula ``text`` as an xlsx file holds it: each function Excel added after 2007 with its ``_xlfn.`` mark."""
    return rename_calls(text, _marked)
