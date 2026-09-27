from pathlib import Path

import pytest

from diagnostics import CleanerError, Reporter
from parser import parse

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def rows_of(name: str, reporter: Reporter | None = None) -> list:
    text = (FIXTURES_DIR / name).read_bytes().decode("utf-8")
    return list(parse(text, ",", reporter or Reporter()))


def values(rows) -> list[list[str]]:
    return [[f.value for f in row.fields] for row in rows]


def warnings_of(reporter: Reporter) -> list[tuple[str, int, int]]:
    return [(d.message, d.line, d.column) for d in reporter.warnings]


# Line endings


@pytest.mark.parametrize("name", ["crlf.csv", "lf.csv", "mixed_endings.csv"])
def test_crlf_and_lf_both_end_rows(name):
    assert values(rows_of(name)) == [["a", "b"], ["1", "2"], ["3", "4"]]


def test_last_row_without_line_ending():
    assert values(rows_of("no_final_newline.csv")) == [["a", "b"], ["1", "2"]]


def test_bare_cr_is_field_data_with_warning():
    reporter = Reporter()
    rows = rows_of("bare_cr.csv", reporter)
    assert values(rows) == [["a", "b"], ["x\ry", "2"]]
    assert warnings_of(reporter) == [("bare carriage return (\\r) kept as field data", 2, 2)]


def test_bare_cr_inside_quotes_is_data_without_warning():
    reporter = Reporter()
    rows = list(parse('a\r\n"x\ry"\r\n', ",", reporter))
    assert values(rows) == [["a"], ["x\ry"]]
    assert reporter.warnings == []


# Quoting


def test_comma_inside_quotes_is_data():
    rows = rows_of("quoted_commas.csv")
    assert values(rows) == [["name", "address"], ["Ada", "12 Main St, Apt 4"]]
    assert rows[1].fields[1].quoted


def test_doubled_quotes_become_one_quote():
    assert values(rows_of("doubled_quotes.csv"))[1:] == [["1", 'She said "hi"'], ["2", '"']]


@pytest.mark.parametrize("name, newline", [("embedded_lf.csv", "\n"), ("embedded_crlf.csv", "\r\n")])
def test_newlines_inside_quotes_are_kept_exactly(name, newline):
    rows = rows_of(name)
    assert values(rows) == [["id", "note"], ["1", f"line one{newline}line two"], ["2", "x"]]
    # Line numbers count physical lines, so the row after the multi-line field is on line 4.
    assert [row.line for row in rows] == [1, 2, 4]


def test_quote_inside_unquoted_field_is_data_with_warning():
    reporter = Reporter()
    rows = rows_of("mid_field_quote.csv", reporter)
    assert values(rows)[1:] == [["5'10\"", "x"], ["1", ' "q"']]
    assert not rows[2].fields[1].quoted
    quote_warning = 'quote (") inside an unquoted field kept as data'
    assert warnings_of(reporter) == [(quote_warning, 2, 5), (quote_warning, 3, 4), (quote_warning, 3, 6)]


def test_unclosed_quote_is_fatal_at_opening_quote():
    with pytest.raises(CleanerError) as exc:
        rows_of("unclosed_quote.csv")
    diagnostic = exc.value.diagnostic
    assert (diagnostic.message, diagnostic.line, diagnostic.column) == ("quoted field is never closed", 3, 3)


def test_character_after_closing_quote_is_fatal():
    with pytest.raises(CleanerError) as exc:
        rows_of("junk_after_quote.csv")
    assert (exc.value.diagnostic.line, exc.value.diagnostic.column) == (2, 6)


# Whitespace


def test_whitespace_is_kept():
    assert values(rows_of("whitespace.csv"))[1] == ["  x ", " y ", "  z  "]


# NULL vs. empty string


def test_unquoted_empty_is_null_and_quoted_empty_is_empty_string():
    rows = rows_of("null_vs_empty.csv")
    assert [[f.is_null for f in row.fields] for row in rows[1:]] == [
        [False, True, False],
        [True, False, True],
    ]
    assert values(rows)[1:] == [["1", "", ""], ["", "", ""]]


# Empty and minimal files


def test_empty_text_has_no_rows():
    assert list(parse("", ",", Reporter())) == []


def test_headers_only():
    assert values(rows_of("headers_only.csv")) == [["id", "name", "zip"]]


def test_blank_lines_are_skipped_with_warning():
    reporter = Reporter()
    rows = rows_of("blank_lines.csv", reporter)
    assert values(rows) == [["a", "b"], ["1", "2"], ["3", "4"]]
    assert [row.line for row in rows] == [1, 3, 5]
    assert warnings_of(reporter) == [("blank line skipped", 2, 1), ("blank line skipped", 4, 1)]


# Values are never changed


def test_numeric_looking_values_are_untouched():
    rows = values(rows_of("numeric_looking.csv"))
    assert rows[1] == ["00501", "40.7128", "-74.0060", "000123456789012345", "1e5", "NaN", "TRUE", "03/04/2025"]
    assert rows[2] == ["007", "-0.0", "0.10", "42", "1E-3", "nan", "false", "2025-04-03"]


# Row metadata used later for error messages and the rejects file


def test_field_positions_and_raw_row():
    rows = rows_of("quoted_commas.csv")
    assert [(f.line, f.column) for f in rows[1].fields] == [(2, 1), (2, 5)]
    assert rows[1].raw == 'Ada,"12 Main St, Apt 4"'


def test_other_delimiters():
    rows = list(parse('a;b\r\n3,14;"x;y"\r\n', ";", Reporter()))
    assert values(rows) == [["a", "b"], ["3,14", "x;y"]]


@pytest.mark.parametrize("delimiter", ['"', "\n", "\r", "", ";;"])
def test_invalid_delimiter_is_rejected(delimiter):
    with pytest.raises(ValueError):
        parse("a", delimiter, Reporter())
