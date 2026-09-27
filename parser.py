"""Quote-aware CSV tokenizer: turns decoded text into rows of fields.

A character-by-character state machine. It doesn't use the csv module, which treats a
bare \\r as a line ending and forgets whether a field was quoted.

The parser only splits text. It never changes a value: trimming, trailing
delimiters, and row-length checks happen in later stages.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator

from diagnostics import CleanerError, Reporter

QUOTE = '"'


class State(Enum):
    FIELD_START = auto()  # nothing read yet for the current field
    UNQUOTED = auto()  # inside a field that didn't start with a quote
    QUOTED = auto()  # inside "...", before the closing quote
    QUOTE_IN_QUOTED = auto()  # just read a quote inside "..." (closing, or first of "")


@dataclass(frozen=True)
class Field:
    value: str
    quoted: bool
    line: int
    column: int

    @property
    def is_null(self) -> bool:
        """An unquoted empty field is NULL; a quoted empty field ("") is an empty string."""
        return not self.quoted and self.value == ""


@dataclass(frozen=True)
class Row:
    fields: tuple[Field, ...]
    line: int  # physical line the row starts on
    raw: str  # the row's source text, without its line ending


def validate_delimiter(delimiter: str) -> None:
    """A delimiter must be one character that can't be confused with quoting or line endings."""
    if len(delimiter) != 1 or delimiter in (QUOTE, "\r", "\n"):
        raise ValueError(f"invalid delimiter: {delimiter!r}")


def parse(text: str, delimiter: str, reporter: Reporter) -> Iterator[Row]:
    """Yield rows lazily, so delimiter sniffing can stop after the first few."""
    validate_delimiter(delimiter)
    return _Tokenizer(text, delimiter, reporter).rows()


class _Tokenizer:
    def __init__(self, text: str, delimiter: str, reporter: Reporter) -> None:
        self.text = text
        self.delimiter = delimiter
        self.reporter = reporter
        self.line = 1
        self.column = 1
        self._start_row(0)

    def rows(self) -> Iterator[Row]:
        text, delimiter = self.text, self.delimiter
        i = 0
        while i < len(text):
            char = text[i]
            if char == "\n":
                ending = 1
            elif char == "\r" and text.startswith("\n", i + 1):
                ending = 2
            else:
                ending = 0

            if self.state is State.QUOTED:
                # Everything up to the next quote is data, line endings included.
                if char == QUOTE:
                    self.state = State.QUOTE_IN_QUOTED
                else:
                    self.chars.append(char)
            elif self.state is State.QUOTE_IN_QUOTED and char == QUOTE:
                self.chars.append(QUOTE)
                self.state = State.QUOTED
            elif char == delimiter:
                self._end_field()
            elif ending:
                row = self._end_row(i)
                if row is not None:
                    yield row
                i += ending
                self.line += 1
                self.column = 1
                self._start_row(i)
                continue
            elif self.state is State.QUOTE_IN_QUOTED:
                raise CleanerError(
                    f"unexpected character {char!r} after closing quote", self.line, self.column
                )
            elif char == QUOTE and self.state is State.FIELD_START:
                self.quoted = True
                self.state = State.QUOTED
            else:
                if char == QUOTE:
                    self._warn('quote (") inside an unquoted field kept as data')
                elif char == "\r":
                    self._warn("bare carriage return (\\r) kept as field data")
                self.chars.append(char)
                self.state = State.UNQUOTED

            if char == "\n":  # only reachable inside a quoted field
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            i += 1

        if self.state is State.QUOTED:
            raise CleanerError("quoted field is never closed", *self.field_position)
        row = self._end_row(len(text))
        if row is not None:
            yield row

    def _start_row(self, offset: int) -> None:
        self.row_offset = offset
        self.row_line = self.line
        self.fields: list[Field] = []
        self._start_field(self.column)

    def _start_field(self, column: int) -> None:
        self.state = State.FIELD_START
        self.chars: list[str] = []
        self.quoted = False
        # Where the field starts. For a quoted field this is also where its quote opened.
        self.field_position = (self.line, column)

    def _end_field(self) -> None:
        """Called on a delimiter. The next field starts right after it."""
        self.fields.append(Field("".join(self.chars), self.quoted, *self.field_position))
        self._start_field(self.column + 1)

    def _end_row(self, end: int) -> Row | None:
        """Finish the current row at text offset `end`, or return None if it is empty."""
        if self.state is State.FIELD_START and not self.fields:
            if end < len(self.text):  # an empty line, not just the end of the file
                self._warn("blank line skipped")
            return None
        self.fields.append(Field("".join(self.chars), self.quoted, *self.field_position))
        return Row(tuple(self.fields), self.row_line, self.text[self.row_offset:end])

    def _warn(self, message: str) -> None:
        self.reporter.warn(message, self.line, self.column)
