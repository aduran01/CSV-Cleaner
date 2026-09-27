"""Serialize cleaned rows (and rejected rows) back to CSV.

Values are never changed here. The writer only decides how each value is
quoted, so that reading the output back gives the same values, NULLs included.
"""

import codecs
from typing import Sequence

from clean import Reject
from diagnostics import Reporter
from parser import QUOTE, Row, validate_delimiter

REJECTS_HEADER = ("line", "reason", "raw_row")


def format_rows(rows: list[Row], reporter: Reporter, *, delimiter: str = ",", line_ending: str = "\r\n") -> str:
    validate_delimiter(delimiter)
    lines = []
    for row in rows:
        cells = [None if field.is_null else field.value for field in row.fields]
        if cells == [None]:
            # A lone NULL would be written as an empty line, which is read back as a blank
            # line and skipped. An empty string is the closest value that survives.
            reporter.warn("row with a single NULL field written as an empty string", row.line, 1)
            cells = [""]
        lines.append(_format_line(cells, delimiter))
    return "".join(line + line_ending for line in lines)


def format_rejects(rejects: list[Reject], *, delimiter: str = ",", line_ending: str = "\r\n") -> str:
    validate_delimiter(delimiter)
    lines = [_format_line(REJECTS_HEADER, delimiter)]
    lines += [_format_line((str(r.line), r.reason, r.raw), delimiter) for r in rejects]
    return "".join(line + line_ending for line in lines)


def encode(text: str, *, bom: bool = False) -> bytes:
    data = text.encode("utf-8")
    return codecs.BOM_UTF8 + data if bom else data


def _format_line(cells: Sequence[str | None], delimiter: str) -> str:
    return delimiter.join(_format_value(cell, delimiter) for cell in cells)


def _format_value(value: str | None, delimiter: str) -> str:
    """NULL is written as nothing. Everything else is quoted only when it has to be."""
    if value is None:
        return ""
    if _needs_quotes(value, delimiter):
        return QUOTE + value.replace(QUOTE, QUOTE * 2) + QUOTE
    return value


def _needs_quotes(value: str, delimiter: str) -> bool:
    return (
        value == ""  # an empty string, as opposed to NULL
        or value[0].isspace()
        or value[-1].isspace()
        or any(char in value for char in (delimiter, QUOTE, "\r", "\n"))
    )
