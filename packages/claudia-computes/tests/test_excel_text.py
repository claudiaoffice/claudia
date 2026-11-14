"""More text functions: CONCATENATE, character codes, cleaning, number formatting as text, REPLACE, TEXTBEFORE/AFTER."""

from __future__ import annotations

from excel_helpers import cases, check, column

TEXT = (
    ('=CONCATENATE("a", "b", 1)', "ab1"),
    ('=CONCATENATE("x")', "x"),
    ('=CONCATENATE(1.5, TRUE, "")', "1.5TRUE"),
    ("=CONCATENATE(A1:A2)", "#VALUE!"),  # (a range is not one text: CONCAT takes ranges)
    ("=CHAR(65)", "A"),
    ("=CHAR(97)", "a"),
    ("=CHAR(10)", "\n"),
    ("=CHAR(233)", "é"),
    ("=CHAR(128)", "€"),
    ("=CHAR(0)", "#VALUE!"),
    ("=CHAR(256)", "#VALUE!"),
    ('=CODE("A")', 65),
    ('=CODE("Apple")', 65),
    ('=CODE("é")', 233),
    ('=CODE("€")', 128),
    ('=CODE("")', "#VALUE!"),
    ("=UNICHAR(65)", "A"),
    ("=UNICHAR(8364)", "€"),
    ("=UNICHAR(128512)", "\U0001f600"),
    ("=UNICHAR(0)", "#VALUE!"),
    ("=UNICHAR(55296)", "#VALUE!"),  # (half of a surrogate pair is no character)
    ("=UNICHAR(1114112)", "#VALUE!"),
    ('=UNICODE("A")', 65),
    ('=UNICODE("€uro")', 8364),
    ('=UNICODE("\U0001f600")', 128512),
    ('=UNICODE("")', "#VALUE!"),
    ('=CLEAN("a" & CHAR(7) & "b" & CHAR(10) & "c")', "abc"),
    ('=CLEAN("plain")', "plain"),
    ('=NUMBERVALUE("2.5")', 2.5),
    ('=NUMBERVALUE("2.500,27", ",", ".")', 2500.27),
    ('=NUMBERVALUE("3.5%")', 0.035),
    ('=NUMBERVALUE("3.5%%")', 0.00035),
    ('=NUMBERVALUE(" 1 234 ")', 1234),
    ('=NUMBERVALUE("1,234.5")', 1234.5),
    ('=NUMBERVALUE("")', 0),
    ('=NUMBERVALUE("-7")', -7),
    ('=NUMBERVALUE("abc")', "#VALUE!"),
    ('=NUMBERVALUE("1.2.3")', "#VALUE!"),
    ('=NUMBERVALUE("1", ".", ".")', "#VALUE!"),
    ("=DOLLAR(1234.567)", "$1,234.57"),
    ("=DOLLAR(1234.567, 0)", "$1,235"),
    ("=DOLLAR(1234.567, -2)", "$1,200"),
    ("=DOLLAR(-1234.567, 1)", "-$1,234.6"),
    ("=DOLLAR(0.5)", "$0.50"),
    ("=FIXED(1234.567, 1)", "1,234.6"),
    ("=FIXED(1234.567, -1)", "1,230"),
    ("=FIXED(-1234.567, 0, TRUE)", "-1235"),
    ("=FIXED(44.332)", "44.33"),
    ("=FIXED(0.5, 0)", "1"),
    ("=FIXED(1234567.891, 2)", "1,234,567.89"),
    ('=REPLACE("abcdefghijk", 6, 5, "*")', "abcde*k"),
    ('=REPLACE("2009", 3, 2, "10")', "2010"),
    ('=REPLACE("123456", 1, 3, "@")', "@456"),
    ('=REPLACE("abc", 4, 0, "d")', "abcd"),
    ('=REPLACE("abc", 2, 10, "")', "a"),
    ('=REPLACE("abc", 0, 1, "x")', "#VALUE!"),
    ('=REPLACE("abc", 1, -1, "x")', "#VALUE!"),
)


@cases(*TEXT)
def test_text_functions(formula, expected, cells):
    check(formula, expected, cells, )


def test_concatenate_reads_cells():
    check('=CONCATENATE(A1, "-", A2)', "x-y", column("A1", ["x", "y"]))


RED = "Little Red Riding Hood's red hood"
BEFORE_AFTER = (
    (f'=TEXTBEFORE("{RED}", "Red")', "Little "),
    (f'=TEXTBEFORE("{RED}", "red")', "Little Red Riding Hood's "),
    (f'=TEXTBEFORE("{RED}", "red", 1, 1)', "Little "),
    (f'=TEXTBEFORE("{RED}", "hood", -1)', "Little Red Riding Hood's red "),
    (f'=TEXTBEFORE("{RED}", "hood", 2)', "#N/A"),  # (only one lower case "hood" in it)
    (f'=TEXTBEFORE("{RED}", "hood", 2, 1)', "Little Red Riding Hood's red "),
    (f'=TEXTBEFORE("{RED}", "hood", 1, 1)', "Little Red Riding "),
    (f'=TEXTBEFORE("{RED}", "x")', "#N/A"),
    (f'=TEXTBEFORE("{RED}", "x", 1, 0, 0, "none")', "none"),
    ('=TEXTBEFORE("abc", "c", 1, 0, 1)', "ab"),
    ('=TEXTBEFORE("abc", "z", 1, 0, 1)', "abc"),
    ('=TEXTBEFORE("abc", "")', ""),
    ('=TEXTBEFORE("abc", "b", 0)', "#VALUE!"),
    ('=TEXTBEFORE("abc", "b", 2)', "#N/A"),
    ('=TEXTBEFORE("abc", "b", 5)', "#VALUE!"),  # (more instances than the text has characters)
    (f'=TEXTAFTER("{RED}", "Red")', " Riding Hood's red hood"),
    (f'=TEXTAFTER("{RED}", "red", 2, 1)', " hood"),
    (f'=TEXTAFTER("{RED}", "hood", -1)', ""),
    (f'=TEXTAFTER("{RED}", "hood")', ""),
    (f'=TEXTAFTER("{RED}", "hood", 1, 1)', "'s red hood"),
    (f'=TEXTAFTER("{RED}", "x")', "#N/A"),
    ('=TEXTAFTER("abc", "a", 1, 0, 0, "-")', "bc"),
    ('=TEXTAFTER("abc", "")', "abc"),
    ('=TEXTAFTER("a-b-c", "-", -1)', "c"),
    ('=TEXTAFTER("a-b-c", "-", -2)', "b-c"),
    ('=TEXTAFTER("abc", "z", 1, 0, 1)', ""),
    ('=TEXTAFTER("abc", "b", 0)', "#VALUE!"),
)


@cases(*BEFORE_AFTER)
def test_textbefore_and_textafter(formula, expected, cells):
    check(formula, expected, cells)


def test_textbefore_and_textafter_split_the_text_in_two():
    for text, delimiter in (("a-b-c", "-"), ("one, two, three", ", "), ("xyz", "y")):
        for instance in (1, 2, -1):
            before = check_value(f'=TEXTBEFORE("{text}", "{delimiter}", {instance}, 0, 0, "#")')
            after = check_value(f'=TEXTAFTER("{text}", "{delimiter}", {instance}, 0, 0, "#")')
            if before != "#" and after != "#":
                assert before + delimiter + after == text, (text, delimiter, instance)


def check_value(formula):
    from excel_helpers import value

    return value(formula)
