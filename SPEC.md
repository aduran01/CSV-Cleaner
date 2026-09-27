# CSV Cleaner — Spec

## The problem

CSV has no single standard in practice. RFC 4180 describes one format, but real files come
from Excel, databases, scripts, and older systems, and each bends the rules in its own way.
The line endings, delimiters, quoting, and encodings all vary, and nothing in the file says
which choices were made. Most parsers quietly guess, and different parsers guess
differently, so the same file can load as different data depending on the tool.

The CSV Cleaner reads one of these messy files and writes a clean, consistent CSV. Every
ambiguous choice is decided explicitly by this spec. **The cleaner never silently changes
data.** If a file can't be read unambiguously, the cleaner reports where the problem is
instead of guessing.

## Non-goals

These are **out of scope**. Don't implement them, even partially, even as optional flags:

- **Type inference or conversion.** Every value is text. No number, date, or boolean parsing.
- **Reformatting values.** No date reformatting, number formatting, case changes, Unicode
  normalization (NFC/NFD), or character replacement.
- **Repairing malformed quoting.** An unclosed quote is an error. The cleaner doesn't guess
  where the field was meant to end.
- **Data-quality work:** deduplicating rows, validating a schema, checking required
  columns, renaming or trimming header names, or reordering columns.
- **Header detection.** The first logical row is always the header.
- **Other dialect features:** quote characters other than `"`, backslash escaping, comment
  lines, and delimiters longer than one character.
- **Other file formats:** `.xlsx`, JSON, Parquet, and so on. Input and output are CSV only.
- **Batch processing:** several input files, merging files, or watching folders.
- **A GUI, a web interface, or a packaged library** (no pip install or public API).
- **Performance tuning** for very large files. Reading the whole file into memory is fine.
- **CLI flags not listed in this spec.**

## Constraints

- Python 3.10+, **standard library only**. No pandas, chardet, or other third-party
  packages at runtime. `pytest` is allowed for tests.
- **Parsing does not use the `csv` module.** It treats a bare `\r` as a line ending and
  throws away whether a field was quoted, which conflicts with the criteria below.
- Diagnostics (warnings and errors) go to **stderr**, never into the output data.
- A fatal error must leave **no** output file behind, and must not modify an existing one.
- It runs on Windows. File handling must not let Python or git rewrite line endings or
  encoding.

## Affected files

All paths are relative to the `CSV Cleaner/` folder.

| File | Purpose |
|---|---|
| `main.py` | CLI entry point: argument parsing, wiring the modules together, exit codes |
| `encoding.py` | Byte-level encoding detection, BOM handling, decoding |
| `sniff.py` | Delimiter detection |
| `parser.py` | Quote-aware tokenizer that produces rows of fields |
| `writer.py` | Serializes rows back to CSV bytes |
| `tests/test_*.py` | pytest tests |
| `tests/fixtures/` | Raw input files for the test cases |
| `.gitattributes` | Marks fixtures as binary so git leaves their bytes alone |

## Acceptance criteria

Each criterion needs at least one fixture and one test. Tests check both the parsed values
and the **exact output bytes**. Error tests also check the reported line and column.

### CLI

- [ ] `python main.py INPUT [-o OUTPUT]` writes cleaned CSV to `OUTPUT`, or to stdout if
      no output file is given.
- [ ] The supported flags are exactly `--delimiter`, `--out-delimiter`, `--encoding`,
      `--lf`, `--bom`, `--strip`, and `--pad-short`, as described below.
- [ ] Exit code `0` means success with no warnings, `1` means success with warnings, and
      `2` means a fatal error with nothing written.
- [ ] Every warning and error names the physical line and column it refers to.

### Encoding

- [ ] A UTF-8, UTF-16 LE/BE, or UTF-32 LE/BE byte-order mark (BOM) is detected, used for
      decoding, and removed. It never ends up as part of the first header name.
- [ ] With no BOM, the file is decoded as strict UTF-8 if possible.
- [ ] If strict UTF-8 fails, the file is decoded as Windows-1252. If it contains a byte that
      cp1252 doesn't define (`0x81 0x8D 0x8F 0x90 0x9D`), it is decoded as Latin-1.
- [ ] The chosen encoding is always reported on stderr. `--encoding` overrides detection.
- [ ] Output is UTF-8 without a BOM. `--bom` adds one.
- [ ] Non-ASCII content (accents, CJK, emoji, right-to-left text) comes through unchanged.

### Delimiter detection

- [ ] Candidates are `,` `;` `\t` `|`. Detection uses the quote-aware parser over the first
      ~50 logical rows, so delimiters inside quoted fields don't count.
- [ ] The winner is the candidate that gives the same field count, greater than 1, on the
      most rows. A tie or no clear winner is a fatal error asking for `--delimiter`.
- [ ] `--delimiter` skips detection entirely.
- [ ] Output uses `,` unless `--out-delimiter` is given.
- [ ] In a semicolon-delimited file, decimal commas such as `3,14` stay as data.

### Line endings

- [ ] `\r\n` and `\n` both end a row, even when mixed in one file.
- [ ] A bare `\r` that isn't followed by `\n` is **literal field data**, not a row end, and
      produces a warning.
- [ ] Output rows end in `\r\n`. `--lf` switches to `\n`.

### Quoting

- [ ] A comma inside a quoted field is part of the value: `"a,b"` → `a,b`.
- [ ] Inside a quoted field, `""` becomes `"`.
- [ ] Newlines inside a quoted field, `\n` or `\r\n`, are kept exactly as written. One
      logical row can span several physical lines.
- [ ] A `"` in the middle of an unquoted field, such as `ab"c` or `a, "b"`, is literal data
      and produces a warning.
- [ ] An unclosed quote is a fatal error that reports where the quote opened.
- [ ] Anything other than a delimiter or row end after a closing quote, such as `"abc"x`,
      is a fatal error.

### Whitespace

- [ ] Spaces and tabs next to delimiters are kept as part of the field value.
- [ ] `--strip` trims leading and trailing whitespace from **unquoted** fields only.
      Whitespace inside quotes is never changed.

### Row shape

- [ ] The header row sets the expected field count.
- [ ] A trailing delimiter is removed only when **every** row, header included, ends with
      an extra empty unquoted field. Removing it produces a warning. If only some rows have
      one, those rows are treated as ragged.
- [ ] By default, ragged rows (too few or too many fields) are left out of the output. They
      are written to a rejects file with the columns `line,reason,raw_row`, and each one
      produces a warning.
- [ ] The rejects file is `<output stem>.rejects.csv`, or `<input stem>.rejects.csv` when
      writing to stdout. It is only created if at least one row is rejected.
- [ ] `--pad-short` fills short rows with NULL fields instead of rejecting them. Rows with
      too many fields are always rejected.
- [ ] A physical line that is completely empty and not inside quotes is skipped with a
      warning.

### NULL vs. empty string

- [ ] An empty field without quotes (`a,,b`) is **NULL**.
- [ ] An empty field with quotes (`a,"",b`) is an **empty string**.
- [ ] The output keeps the difference: NULL is written as nothing, and an empty string is
      written as `""`.

### Empty and minimal files

- [ ] A 0-byte file produces empty output, a warning, and exit code `1`.
- [ ] A file with only a header is valid. The output is just the cleaned header row.

### Values are never changed

- [ ] Leading zeros (`00501`), coordinates (`40.7128`, `-74.0060`), `-0.0`, `1e5`, `NaN`,
      `TRUE`, long IDs, and dates in any format come out exactly as they went in.

### Output format

- [ ] A field is quoted only if it contains the output delimiter, `"`, `\r`, or `\n`, has
      leading or trailing whitespace, or is an empty string rather than NULL.
- [ ] Every `"` inside a quoted field is written as `""`.
- [ ] **Running the cleaner on its own output gives identical bytes.** This is tested
      against every fixture.
