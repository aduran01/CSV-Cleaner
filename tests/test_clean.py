from pathlib import Path

from clean import Reject, clean
from diagnostics import Reporter
from parser import parse

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def clean_fixture(name: str, reporter: Reporter | None = None, **options):
    text = (FIXTURES_DIR / name).read_bytes().decode("utf-8")
    reporter = reporter or Reporter()
    return clean(list(parse(text, ",", reporter)), reporter, **options)


def values(result) -> list[list[str]]:
    return [[f.value for f in row.fields] for row in result.rows]


def warnings_of(reporter: Reporter) -> list[tuple[str, int, int]]:
    return [(d.message, d.line, d.column) for d in reporter.warnings]


# Trailing delimiter


def test_trailing_delimiter_on_every_row_is_removed_with_warning():
    reporter = Reporter()
    result = clean_fixture("trailing_delimiter_all.csv", reporter)
    assert values(result) == [["a", "b"], ["1", "2"], ["3", ""]]
    assert result.rows[2].fields[1].is_null
    assert warnings_of(reporter) == [("trailing delimiter removed from every row", 1, 4)]


def test_trailing_delimiter_on_some_rows_makes_them_ragged():
    reporter = Reporter()
    result = clean_fixture("trailing_delimiter_some.csv", reporter)
    assert values(result) == [["a", "b"], ["3", "4"]]
    assert result.rejects == [Reject(2, "expected 2 fields, found 3", "1,2,")]


def test_quoted_empty_last_field_is_not_a_trailing_delimiter():
    result = clean_fixture("trailing_quoted_empty.csv")
    assert values(result) == [["a", "b", ""], ["1", "2", ""]]


def test_single_column_of_nulls_is_not_a_trailing_delimiter():
    reporter = Reporter()
    rows = list(parse("a\r\nx\r\n", ",", reporter))
    assert values(clean(rows, reporter)) == [["a"], ["x"]]


def test_trailing_delimiter_is_checked_before_strip():
    reporter = Reporter()
    rows = list(parse("a,b, \r\n1,2, \r\n", ",", reporter))
    result = clean(rows, reporter, strip=True)
    # The last field held a space, so it is a real (now NULL) column.
    assert values(result) == [["a", "b", ""], ["1", "2", ""]]
    assert reporter.warnings == []


# Whitespace


def test_whitespace_is_kept_by_default():
    assert values(clean_fixture("whitespace.csv"))[1] == ["  x ", " y ", "  z  "]


def test_strip_trims_unquoted_fields_only():
    assert values(clean_fixture("whitespace.csv", strip=True))[1] == ["x", "y", "  z  "]


def test_strip_leaves_other_whitespace_alone():
    reporter = Reporter()
    rows = list(parse("a\r\n x\t \r\n", ",", reporter))
    assert values(clean(rows, reporter, strip=True))[1] == [" x"]


def test_strip_can_turn_a_blank_field_into_null():
    reporter = Reporter()
    rows = list(parse("a,b\r\n1,   \r\n", ",", reporter))
    result = clean(rows, reporter, strip=True)
    assert result.rows[1].fields[1].is_null


# Ragged rows


def test_ragged_rows_are_rejected_with_warnings():
    reporter = Reporter()
    result = clean_fixture("ragged.csv", reporter)
    assert values(result) == [["a", "b", "c"], ["5", "6", "7"]]
    assert result.rejects == [
        Reject(2, "expected 3 fields, found 2", "1,2"),
        Reject(3, "expected 3 fields, found 4", "1,2,3,4"),
    ]
    assert warnings_of(reporter) == [
        ("row rejected: expected 3 fields, found 2", 2, 1),
        ("row rejected: expected 3 fields, found 4", 3, 1),
    ]


def test_pad_short_fills_short_rows_with_null_but_still_rejects_long_rows():
    reporter = Reporter()
    result = clean_fixture("ragged.csv", reporter, pad_short=True)
    assert values(result) == [["a", "b", "c"], ["1", "2", ""], ["5", "6", "7"]]
    assert result.rows[1].fields[2].is_null
    assert [r.line for r in result.rejects] == [3]
    assert ("row padded from 2 to 3 fields with NULL", 2, 1) in warnings_of(reporter)


def test_rejected_multiline_row_keeps_its_raw_text():
    reporter = Reporter()
    rows = list(parse('a,b\r\n"x\r\ny"\r\n', ",", reporter))
    assert clean(rows, reporter).rejects == [Reject(2, "expected 2 fields, found 1", '"x\r\ny"')]


# Empty and minimal files


def test_no_rows():
    result = clean([], Reporter())
    assert (result.rows, result.rejects) == ([], [])


def test_headers_only():
    result = clean_fixture("headers_only.csv")
    assert values(result) == [["id", "name", "zip"]]
    assert result.rejects == []
