from pathlib import Path

import pytest

from build_fixtures import FIXTURES
from diagnostics import CleanerError, Reporter
from encoding import decode

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def read(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def test_fixtures_on_disk_match_their_source():
    # Catches git or an editor rewriting line endings or encoding.
    for name, data in FIXTURES.items():
        assert read(name) == data, name


@pytest.mark.parametrize(
    "name, encoding",
    [
        ("utf8_bom.csv", "utf-8"),
        ("utf16le_bom.csv", "utf-16-le"),
        ("utf16be_bom.csv", "utf-16-be"),
        ("utf32le_bom.csv", "utf-32-le"),
    ],
)
def test_bom_is_detected_and_removed(name, encoding):
    decoded = decode(read(name), Reporter())
    assert decoded.encoding == encoding
    assert decoded.had_bom
    assert decoded.text == "id,name\r\n1,Zoë\r\n"


def test_utf8_without_bom():
    decoded = decode(read("utf8_multilingual.csv"), Reporter())
    assert decoded.encoding == "utf-8"
    assert not decoded.had_bom
    assert "北京" in decoded.text
    assert "\U0001f389" in decoded.text


def test_falls_back_to_cp1252():
    decoded = decode(read("cp1252.csv"), Reporter())
    assert decoded.encoding == "cp1252"
    assert decoded.text == "item,price\r\ncafé,€5\r\n"


def test_falls_back_to_latin1_when_cp1252_byte_is_undefined():
    decoded = decode(read("latin1.csv"), Reporter())
    assert decoded.encoding == "latin-1"
    assert decoded.text == "code,label\r\n\x81,naïve\r\n"


def test_empty_input_decodes_to_empty_text():
    assert decode(read("empty.csv"), Reporter()).text == ""


def test_chosen_encoding_is_reported():
    reporter = Reporter()
    decode(read("cp1252.csv"), reporter)
    assert [d.message for d in reporter.diagnostics] == ["encoding: cp1252 (input is not valid UTF-8)"]
    assert reporter.warnings == []


def test_override_wins_over_detection():
    decoded = decode(read("cp1252.csv"), Reporter(), override="latin-1")
    assert decoded.encoding == "iso8859-1"
    assert decoded.text == "item,price\r\ncafé,\x805\r\n"


def test_override_strips_bom():
    decoded = decode(read("utf8_bom.csv"), Reporter(), override="utf-8")
    assert decoded.had_bom
    assert decoded.text.startswith("id,")


def test_override_that_cannot_decode_reports_position():
    with pytest.raises(CleanerError) as exc:
        decode(read("cp1252.csv"), Reporter(), override="utf-8")
    assert (exc.value.diagnostic.line, exc.value.diagnostic.column) == (2, 4)


def test_unknown_override_is_fatal():
    with pytest.raises(CleanerError):
        decode(b"a\r\n", Reporter(), override="not-a-codec")
