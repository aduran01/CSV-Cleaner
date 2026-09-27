"""CSV Cleaner command line: python main.py INPUT [-o OUTPUT] [options]

Exit codes: 0 success, 1 success with warnings, 2 fatal error (nothing written).
"""

import argparse
import os
import sys
from pathlib import Path

from diagnostics import CleanerError, Reporter
from pipeline import Options, run

# Typing a real tab on the command line is awkward, so these spellings are accepted too.
DELIMITER_ALIASES = {"\\t": "\t", "tab": "\t"}


def main(argv: list[str] | None = None) -> int:
    # Diagnostics can quote any character from the input. Don't crash on a console
    # that can't display it.
    sys.stderr.reconfigure(errors="backslashreplace")
    args = _parse_args(argv)
    reporter = Reporter()
    try:
        output = run(_read(args.input), _options(args), reporter)
        rejects_path = _rejects_path(args.input, args.output) if output.rejects is not None else None
        _write_all(args.output, output.data, rejects_path, output.rejects)
    except CleanerError as exc:
        reporter.flush()
        print(exc.diagnostic.format(), file=sys.stderr)
        return 2
    if rejects_path is not None:
        reporter.info(f"rejected rows written to {rejects_path}")
    exit_code = 1 if reporter.warnings else 0
    reporter.flush()
    return exit_code


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Clean a messy CSV file into consistent RFC 4180-style CSV.",
    )
    parser.add_argument("input", type=Path, help="the CSV file to clean")
    parser.add_argument("-o", "--output", type=Path, help="where to write the result (default: stdout)")
    parser.add_argument("--delimiter", help="input delimiter; skips detection (use \\t or tab for tab)")
    parser.add_argument("--out-delimiter", default=",", help="output delimiter (default: ,)")
    parser.add_argument("--encoding", help="input encoding; skips detection")
    parser.add_argument("--lf", action="store_true", help="end output rows with \\n instead of \\r\\n")
    parser.add_argument("--bom", action="store_true", help="start the output with a UTF-8 byte-order mark")
    parser.add_argument("--strip", action="store_true", help="trim spaces and tabs around unquoted fields")
    parser.add_argument("--pad-short", action="store_true", help="fill short rows with NULL instead of rejecting them")
    return parser.parse_args(argv)


def _options(args: argparse.Namespace) -> Options:
    return Options(
        delimiter=DELIMITER_ALIASES.get(args.delimiter, args.delimiter),
        out_delimiter=DELIMITER_ALIASES.get(args.out_delimiter, args.out_delimiter),
        encoding=args.encoding,
        lf=args.lf,
        bom=args.bom,
        strip=args.strip,
        pad_short=args.pad_short,
    )


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CleanerError(f"cannot read {path}: {exc.strerror}") from None


def _rejects_path(input_path: Path, output_path: Path | None) -> Path:
    base = output_path if output_path is not None else input_path
    return base.with_name(f"{base.stem}.rejects.csv")


def _write_all(output_path: Path | None, data: bytes, rejects_path: Path | None, rejects: bytes | None) -> None:
    """Write every output only after the whole file has been processed.

    Each file goes to a temporary name first and is renamed into place, so a
    failure partway through never leaves a half-written file behind.
    """
    staged = []
    try:
        for path, content in ((rejects_path, rejects), (output_path, data)):
            if path is not None:
                temp = path.with_name(path.name + ".tmp")
                staged.append((temp, path))  # before writing, so a failed write is cleaned up
                temp.write_bytes(content)
        for temp, path in staged:
            os.replace(temp, path)
    except OSError as exc:
        for temp, _ in staged:
            temp.unlink(missing_ok=True)
        raise CleanerError(f"cannot write {exc.filename}: {exc.strerror}") from None
    if output_path is None:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    sys.exit(main())
