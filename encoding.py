"""Detect the input's encoding from raw bytes and decode it to text.

CSV files carry no encoding metadata, so the order of checks is:
byte-order mark, then strict UTF-8, then Windows-1252, then Latin-1.
"""

import codecs
from dataclasses import dataclass

from diagnostics import CleanerError, Reporter

# The UTF-32 marks must be checked before UTF-16: the UTF-32 LE mark
# (FF FE 00 00) starts with the UTF-16 LE mark (FF FE).
_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)


@dataclass(frozen=True)
class DecodedText:
    text: str
    encoding: str
    had_bom: bool


def decode(data: bytes, reporter: Reporter, override: str | None = None) -> DecodedText:
    """Decode raw file bytes, reporting which encoding was used."""
    if override is not None:
        return _decode_override(data, override, reporter)

    for bom, name in _BOMS:
        if data.startswith(bom):
            text = _strict_decode(data[len(bom):], name)
            reporter.info(f"encoding: {name} (byte-order mark found and removed)")
            return DecodedText(text, name, had_bom=True)

    try:
        text, name = data.decode("utf-8"), "utf-8"
        reporter.info("encoding: utf-8")
    except UnicodeDecodeError:
        # Python's cp1252 codec rejects the five bytes cp1252 leaves undefined
        # (0x81 0x8D 0x8F 0x90 0x9D), which is exactly when Latin-1 takes over.
        try:
            text, name = data.decode("cp1252"), "cp1252"
        except UnicodeDecodeError:
            text, name = data.decode("latin-1"), "latin-1"
        reporter.info(f"encoding: {name} (input is not valid UTF-8)")
    return DecodedText(text, name, had_bom=False)


def _decode_override(data: bytes, override: str, reporter: Reporter) -> DecodedText:
    try:
        name = codecs.lookup(override).name
    except LookupError:
        raise CleanerError(f"unknown encoding: {override!r}") from None
    text = _strict_decode(data, name)
    # Codecs like "utf-8" leave a byte-order mark in the text as U+FEFF.
    had_bom = text.startswith("﻿")
    if had_bom:
        text = text[1:]
    reporter.info(f"encoding: {name} (set by --encoding)")
    return DecodedText(text, name, had_bom)


def _strict_decode(data: bytes, name: str) -> str:
    try:
        return data.decode(name)
    except UnicodeDecodeError as exc:
        line, column = _position(data, exc.start, name)
        raise CleanerError(
            f"input is not valid {name} (byte 0x{data[exc.start]:02X})", line, column
        ) from None


def _position(data: bytes, offset: int, name: str) -> tuple[int, int]:
    """Physical line and column of a byte offset. Only \\n and \\r\\n end a line."""
    prefix = data[:offset].decode(name, errors="replace")
    line = prefix.count("\n") + 1
    column = len(prefix) - (prefix.rfind("\n") + 1) + 1
    return line, column
