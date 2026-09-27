import pytest

from build_fixtures import FIXTURES
from diagnostics import CleanerError, Reporter
from pipeline import Options, run

# Fixtures that must stop with a fatal error instead of producing output.
FATAL = {"unclosed_quote.csv", "junk_after_quote.csv", "ambiguous_delimiter.csv"}


def test_fatal_fixtures_are_fatal():
    for name in FATAL:
        with pytest.raises(CleanerError):
            run(FIXTURES[name], Options(), Reporter())


@pytest.mark.parametrize("name", sorted(set(FIXTURES) - FATAL))
@pytest.mark.parametrize(
    "options",
    [Options(), Options(strip=True, pad_short=True), Options(lf=True, bom=True, out_delimiter=";")],
    ids=["default", "strip-pad", "lf-bom-semicolon"],
)
def test_cleaning_the_output_again_gives_identical_bytes(name, options):
    once = run(FIXTURES[name], options, Reporter()).data
    # The second run detects everything again (encoding, BOM, delimiter) from the output.
    again = run(once, options, Reporter())
    assert again.data == once
    assert again.rejects is None


def test_semicolon_file_with_decimal_commas():
    output = run(FIXTURES["semicolon_decimal_comma.csv"], Options(), Reporter())
    assert output.data == b'item,price,weight\r\napple,"3,14","0,5"\r\npear,"2,50","1,25"\r\n'


def test_cp1252_input_becomes_utf8_output():
    output = run(FIXTURES["cp1252.csv"], Options(), Reporter())
    assert output.data == "item,price\r\ncafé,€5\r\n".encode("utf-8")


def test_bom_is_not_carried_into_the_header():
    output = run(FIXTURES["utf16le_bom.csv"], Options(), Reporter())
    assert output.data == "id,name\r\n1,Zoë\r\n".encode("utf-8")


def test_empty_input_warns_and_produces_empty_output():
    reporter = Reporter()
    output = run(b"", Options(), reporter)
    assert (output.data, output.rejects) == (b"", None)
    assert [d.message for d in reporter.warnings] == ["input is empty"]


def test_rejects_are_formatted_with_the_output_options():
    output = run(FIXTURES["ragged.csv"], Options(lf=True, out_delimiter=";"), Reporter())
    assert output.data == b"a;b;c\n5;6;7\n"
    assert output.rejects == (
        b"line;reason;raw_row\n"
        b'2;"expected 3 fields, found 2";"1,2"\n'
        b'3;"expected 3 fields, found 4";"1,2,3,4"\n'
    )


def test_explicit_delimiter_skips_detection():
    reporter = Reporter()
    # Detection would fail on this file; an explicit delimiter makes it unambiguous.
    output = run(FIXTURES["ambiguous_delimiter.csv"], Options(delimiter="|"), reporter)
    assert output.data == b'"a,b",c\r\n"1,2",3\r\n'
    assert not any(d.message.startswith("delimiter:") for d in reporter.diagnostics)


@pytest.mark.parametrize("options", [Options(delimiter='"'), Options(out_delimiter="ab")])
def test_invalid_delimiters_are_fatal(options):
    with pytest.raises(CleanerError):
        run(b"a,b\r\n", options, Reporter())
