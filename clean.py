"""Apply the file-wide cleaning rules to parsed rows.

The parser works one row at a time. These rules need the whole file first:
a trailing delimiter is only removed if every row has one, and the header
sets the field count every other row is checked against.
"""

from dataclasses import dataclass, replace

from diagnostics import Reporter
from parser import Field, Row

# --strip trims spaces and tabs only. Other whitespace, such as a bare \r or a
# non-breaking space, is data the user may want kept.
STRIP_CHARS = " \t"


@dataclass(frozen=True)
class Reject:
    line: int
    reason: str
    raw: str


@dataclass(frozen=True)
class CleanResult:
    rows: list[Row]  # the header first, if the file has one
    rejects: list[Reject]


def clean(rows: list[Row], reporter: Reporter, *, strip: bool = False, pad_short: bool = False) -> CleanResult:
    if not rows:
        return CleanResult([], [])
    rows = _remove_trailing_delimiter(rows, reporter)
    if strip:
        rows = [_strip_row(row) for row in rows]
    return _check_row_lengths(rows, reporter, pad_short)


def _remove_trailing_delimiter(rows: list[Row], reporter: Reporter) -> list[Row]:
    """Drop the last field of every row, but only if every row, header included, ends in an
    extra NULL field. Checked before --strip, so `a,b, ` has a real last field
    holding a space, not a trailing delimiter."""
    if not all(len(row.fields) > 1 and row.fields[-1].is_null for row in rows):
        return rows
    header_end = rows[0].fields[-1]
    reporter.warn("trailing delimiter removed from every row", header_end.line, header_end.column - 1)
    return [replace(row, fields=row.fields[:-1]) for row in rows]


def _strip_row(row: Row) -> Row:
    fields = tuple(
        field if field.quoted else replace(field, value=field.value.strip(STRIP_CHARS))
        for field in row.fields
    )
    return replace(row, fields=fields)


def _check_row_lengths(rows: list[Row], reporter: Reporter, pad_short: bool) -> CleanResult:
    header, *data = rows
    expected = len(header.fields)
    kept = [header]
    rejects = []
    for row in data:
        found = len(row.fields)
        if found == expected:
            kept.append(row)
        elif found < expected and pad_short:
            kept.append(_pad(row, expected))
            reporter.warn(f"row padded from {found} to {expected} fields with NULL", row.line, 1)
        else:
            reason = f"expected {expected} fields, found {found}"
            rejects.append(Reject(row.line, reason, row.raw))
            reporter.warn(f"row rejected: {reason}", row.line, 1)
    return CleanResult(kept, rejects)


def _pad(row: Row, expected: int) -> Row:
    last = row.fields[-1]
    # Padding fields don't exist in the source, so they point just past the row's last field.
    filler = Field("", quoted=False, line=last.line, column=last.column + len(last.value))
    return replace(row, fields=row.fields + (filler,) * (expected - len(row.fields)))
