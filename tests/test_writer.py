from pathlib import Path

import pytest

from clean import Reject, clean
from diagnostics import Reporter
from parser import parse
from writer import encode, format_rejects, format_rows

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def rewrite(text: str, reporter: Reporter | None = None, **options) -> str:
    reporter = reporter or Reporter()
    rows = clean(list(parse(text, ",", reporter)), reporter).rows
    return format_rows(rows, reporter, **options)


# Quoting


@pytest.mark.parametrize(
    "value, written",
    [
        ("plain", "plain"),
        ("a,b", '"a,b"'),
        ('say "hi"', '"say ""hi"""'),
        ("two\nlines", '"two\nlines"'),
        ("two\r\nlines", '"two\r\nlines"'),
        ("bare\rcr", '"bare\rcr"'),
        (" lead", '" lead"'),
        ("trail\t", '"trail\t"'),
        ("in side", "in side"),
        ("00501", "00501"),
        ("São Paulo", "São Paulo"),
    ],
)
def test_fields_are_quoted_only_when_needed(value, written):
    # The source always quotes the value, so this also checks unneeded quotes are dropped.
    source = 'x\r\n"' + value.replace('"', '""') + '"\r\n'
    assert rewrite(source) == "x\r\n" + written + "\r\n"


def test_null_is_written_as_nothing_and_empty_string_as_quotes():
    assert rewrite('a,b,c\r\n1,,""\r\n,"",\r\n') == 'a,b,c\r\n1,,""\r\n,"",\r\n'


def test_single_null_field_row_becomes_empty_string_with_warning():
    reporter = Reporter()
    # --strip turns the spaces into NULL, the only way a one-column row can hold NULL.
    rows = clean(list(parse("a\r\n   \r\n", ",", reporter)), reporter, strip=True).rows
    assert format_rows(rows, reporter) == 'a\r\n""\r\n'
    assert [(d.message, d.line) for d in reporter.warnings] == [
        ("row with a single NULL field written as an empty string", 2)
    ]


# Options


def test_lf_line_endings():
    assert rewrite("a,b\r\n1,2\r\n", line_ending="\n") == "a,b\n1,2\n"


def test_line_ending_option_does_not_touch_newlines_inside_fields():
    assert rewrite('a\r\n"x\r\ny"\r\n', line_ending="\n") == 'a\n"x\r\ny"\n'


def test_output_delimiter():
    reporter = Reporter()
    rows = list(parse("a;b\r\n3,14;x\r\n", ";", reporter))
    # With comma as the output delimiter, the decimal comma now needs quotes.
    assert format_rows(rows, reporter) == 'a,b\r\n"3,14",x\r\n'
    assert format_rows(rows, reporter, delimiter="\t") == "a\tb\r\n3,14\tx\r\n"


def test_invalid_output_delimiter():
    with pytest.raises(ValueError):
        format_rows([], Reporter(), delimiter='"')


def test_no_rows_is_empty_text():
    assert format_rows([], Reporter()) == ""


def test_encode_is_utf8_without_bom_by_default():
    assert encode("Zoë") == b"Zo\xc3\xab"
    assert encode("Zoë", bom=True) == b"\xef\xbb\xbfZo\xc3\xab"


# Rejects file


def test_rejects_file_is_valid_csv_with_original_text():
    rejects = [Reject(2, "expected 2 fields, found 3", '1,"a\r\nb",3')]
    assert format_rejects(rejects) == (
        'line,reason,raw_row\r\n2,"expected 2 fields, found 3","1,""a\r\nb"",3"\r\n'
    )


def test_rejects_file_round_trips_through_the_parser():
    rejects = [Reject(7, "expected 3 fields, found 1", 'x "y"')]
    rows = list(parse(format_rejects(rejects), ",", Reporter()))
    assert [f.value for f in rows[1].fields] == ["7", "expected 3 fields, found 1", 'x "y"']


# Idempotence: cleaning the output again gives the same text


@pytest.mark.parametrize(
    "name",
    [
        "crlf.csv",
        "bare_cr.csv",
        "quoted_commas.csv",
        "doubled_quotes.csv",
        "embedded_lf.csv",
        "embedded_crlf.csv",
        "mid_field_quote.csv",
        "whitespace.csv",
        "null_vs_empty.csv",
        "headers_only.csv",
        "utf8_multilingual.csv",
        "numeric_looking.csv",
        "trailing_delimiter_all.csv",
        "ragged.csv",
    ],
)
def test_cleaning_the_output_again_changes_nothing(name):
    once = rewrite((FIXTURES_DIR / name).read_bytes().decode("utf-8"))
    assert rewrite(once) == once
