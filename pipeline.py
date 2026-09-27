"""Run every stage on the input bytes: decode, detect the delimiter, parse, clean, format.

No file or console I/O happens here, so tests can check the whole pipeline
directly and main.py only handles arguments, files, and exit codes.
"""

from dataclasses import dataclass

from clean import clean
from diagnostics import CleanerError, Reporter
from encoding import decode
from parser import parse
from sniff import detect_delimiter
from writer import encode, format_rejects, format_rows


@dataclass(frozen=True)
class Options:
    delimiter: str | None = None  # None means detect it
    out_delimiter: str = ","
    encoding: str | None = None  # None means detect it
    lf: bool = False
    bom: bool = False
    strip: bool = False
    pad_short: bool = False


@dataclass(frozen=True)
class Output:
    data: bytes
    rejects: bytes  # always present: just the header row when nothing was rejected
    rejected_count: int


def run(data: bytes, options: Options, reporter: Reporter) -> Output:
    """Clean one file's bytes. Raises CleanerError on anything fatal."""
    text = decode(data, reporter, options.encoding).text
    if not text:
        reporter.warn("input is empty", 1, 1)

    delimiter = options.delimiter
    if delimiter is None:
        delimiter = detect_delimiter(text, reporter)

    line_ending = "\n" if options.lf else "\r\n"
    try:
        rows = list(parse(text, delimiter, reporter))
        result = clean(rows, reporter, strip=options.strip, pad_short=options.pad_short)
        cleaned = format_rows(result.rows, reporter, delimiter=options.out_delimiter, line_ending=line_ending)
        rejects = format_rejects(result.rejects, delimiter=options.out_delimiter, line_ending=line_ending)
    except ValueError as exc:  # an invalid --delimiter or --out-delimiter
        raise CleanerError(str(exc)) from None

    return Output(encode(cleaned, bom=options.bom), encode(rejects, bom=options.bom), len(result.rejects))
