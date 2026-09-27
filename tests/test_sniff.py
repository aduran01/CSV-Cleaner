from itertools import chain
from pathlib import Path

import pytest

from diagnostics import CleanerError, Reporter
from sniff import SAMPLE_ROWS, detect_delimiter

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def text_of(name: str) -> str:
    return (FIXTURES_DIR / name).read_bytes().decode("utf-8")


@pytest.mark.parametrize(
    "name, delimiter",
    [
        ("crlf.csv", ","),
        ("semicolon_decimal_comma.csv", ";"),
        ("tab.csv", "\t"),
        ("pipe.csv", "|"),
    ],
)
def test_detects_each_candidate(name, delimiter):
    assert detect_delimiter(text_of(name), Reporter()) == delimiter


def test_delimiters_inside_quotes_do_not_count():
    assert detect_delimiter(text_of("quoted_delimiters.csv"), Reporter()) == ";"


def test_tie_goes_to_the_candidate_with_fewer_warnings():
    assert detect_delimiter(text_of("quotes_break_tie.csv"), Reporter()) == ";"


def test_true_tie_is_fatal():
    with pytest.raises(CleanerError) as exc:
        detect_delimiter(text_of("ambiguous_delimiter.csv"), Reporter())
    assert "comma and pipe" in exc.value.diagnostic.message
    assert "--delimiter" in exc.value.diagnostic.message


def test_single_column_defaults_to_comma():
    reporter = Reporter()
    assert detect_delimiter(text_of("single_column.csv"), reporter) == ","
    assert reporter.warnings == []


def test_empty_text_defaults_to_comma():
    assert detect_delimiter("", Reporter()) == ","


def test_parse_error_for_every_candidate_is_fatal_and_explained():
    with pytest.raises(CleanerError) as exc:
        detect_delimiter('a,b\r\n"never closed\r\n', Reporter())
    assert "never closed" in exc.value.diagnostic.message


def test_detection_is_reported_as_info_not_warning():
    reporter = Reporter()
    detect_delimiter(text_of("tab.csv"), reporter)
    assert [d.message for d in reporter.diagnostics] == ["delimiter: tab (detected)"]
    assert reporter.warnings == []


def test_only_the_sample_is_used():
    # Rows past the sample are pipe-delimited, but only the first SAMPLE_ROWS count.
    lines = chain(["a;b"] * SAMPLE_ROWS, ["a|b|c|d"] * (SAMPLE_ROWS * 2))
    assert detect_delimiter("\r\n".join(lines), Reporter()) == ";"
