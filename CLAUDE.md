# CSV Cleaner — Repository Rules

A command-line tool that reads messy real-world CSV files and writes a clean, consistent,
RFC 4180–style CSV. The guiding principle: **never silently change data.** Every decision
below is explicit, and anything the cleaner can't handle unambiguously is reported, not guessed.

## Project conventions

- Python 3.10+, **standard library only** (no pandas, no chardet). Tests use `pytest`.
- `main.py` is the CLI entry point. Keep the logic in small modules beside it:
  - `encoding.py` — byte-level decoding and BOM handling
  - `sniff.py` — delimiter detection
  - `parser.py` — the tokenizer / state machine
  - `writer.py` — output serialization
  - `tests/` — pytest tests plus `tests/fixtures/` input files
- **Do not use the `csv` module for parsing.** It treats a bare `\r` as a line ending and
  throws away whether a field was quoted — both conflict with the rules below. The parser
  is a hand-written character-by-character state machine (states such as `FIELD_START`,
  `UNQUOTED`, `QUOTED`, `QUOTE_IN_QUOTED`).
- The parser returns rows of `Field` objects that record at least `value: str` and
  `quoted: bool`, plus the source line/column for error messages.
- Warnings and errors go to **stderr** with line and column numbers. Clean data goes to
  stdout or the output file. Never print diagnostics into the data stream.
- Exit codes: `0` success, `1` success with warnings, `2` fatal error (nothing written).

## Parsing rules (decided — don't change without updating this file)

| Case | Rule |
|---|---|
| **Line endings** | Accept both `\r\n` and `\n` as row terminators, even mixed in one file. Output uses `\r\n` (RFC 4180) by default; `--lf` switches to `\n`. |
| **Bare `\r`** (not followed by `\n`) | **Literal field data**, not a row terminator (RFC-strict, like Go/Ruby/PostgreSQL). Emit a warning with its location. This is a deliberate choice — don't inherit Python's universal-newline behavior. |
| **Commas in quoted fields** | Part of the value. `"a,b"` → `a,b`. |
| **Doubled quotes** | Inside a quoted field, `""` → `"`. |
| **Newlines inside quoted fields** | Part of the value, preserved exactly as they appear (`\n` or `\r\n`). One logical row may span many physical lines; line numbers in messages refer to physical lines. |
| **Whitespace around delimiters** | **Preserved** (RFC 4180: spaces are part of the field). `--strip` trims *unquoted* fields only; off by default. Whitespace inside quotes is never touched. |
| **Quote in the middle of an unquoted field** | e.g. `ab"c` or `a, "b"` (space before the quote). Treat the quote as literal data and warn. |
| **Unclosed quote** | **Fatal error** reporting where the quote opened. No guessing where the field ends. |
| **Characters after a closing quote** | e.g. `"abc"x,`. Fatal error — malformed field. |
| **Trailing delimiter** | Strip it only if **every** row, header included, ends with an extra empty unquoted field. Otherwise leave rows alone and let the ragged-row rule deal with them. Report when stripping. |
| **Ragged rows** | The header sets the field count. Rows with a different count are **not** padded or truncated by default; they go to a rejects file (`<output>.rejects.csv`) with line number and reason, plus a warning. `--pad-short` fills short rows with NULL fields; long rows are always rejected. |
| **NULL vs. empty string** | PostgreSQL convention: an **unquoted empty** field (`a,,b`) is NULL; a **quoted empty** field (`a,"",b`) is an empty string. The parser must keep the distinction (`Field.quoted`) and the writer must write it back the same way. |
| **Empty file** (0 bytes) | Write empty output, warn, exit `1`. |
| **Headers-only file** | Valid. Output the cleaned header row and nothing else. |
| **Blank lines** | A completely empty physical line outside quotes is skipped with a warning (it isn't a one-field NULL row). |

## Delimiter sniffing

- Candidates: `,` `;` `\t` `|`. An explicit `--delimiter` always wins and skips sniffing.
- Sniff over the first ~50 logical rows **using the real quote-aware parser**, so delimiters
  inside quoted fields don't count.
- Pick the candidate that gives a field count that is consistent and greater than 1 across
  the most rows. If no candidate clearly wins, or two tie, **fail** and ask for `--delimiter`.
- Semicolon files are usually from decimal-comma locales (e.g. `3,14`). Those commas are
  data, so never rewrite them.
- Output always uses `,` unless `--out-delimiter` says otherwise.

## Values are strings. Never coerce types.

- The cleaner does **no** type inference. Every field is written back exactly as its text.
- Leading zeros (`00501`, `007`), coordinates (`40.7128,-74.0060`, `-0.0`), large IDs,
  `1e5`, `NaN`, `TRUE`, and dates in any format stay exactly as they are.
- Never parse, reformat, or normalize dates or numbers. No float round-trips anywhere.

## Encoding

CSV carries no encoding metadata, so detection happens on raw bytes, in this order:

1. **BOM:** UTF-8 (`EF BB BF`), UTF-16 LE/BE, UTF-32 LE/BE → decode accordingly and strip
   the BOM. It must never end up glued to the first header name.
2. **No BOM:** try strict UTF-8.
3. **UTF-8 fails:** fall back to **Windows-1252**. If a byte is undefined in cp1252
   (`0x81 0x8D 0x8F 0x90 0x9D`), use **Latin-1**.
4. Always report which encoding was chosen (stderr). `--encoding` overrides detection.

Output is **UTF-8 without a BOM** by default; `--bom` adds one (useful for Excel).
Never apply Unicode normalization (NFC/NFD), case folding, or character replacement.
Non-ASCII content (accents, CJK, emoji, RTL text) must survive byte-for-byte after re-encoding.

## Output rules (writer)

- Quote a field if it contains the output delimiter, `"`, `\r`, or `\n`, or has leading or
  trailing whitespace. Also quote it if it's an empty string rather than NULL. Otherwise
  leave it unquoted.
- Escape `"` as `""`.
- **Idempotence:** running the cleaner on its own output must produce identical bytes.
  This is a required test for every fixture.

## Testing rules

- Every case in this file has at least one fixture in `tests/fixtures/` and a test that
  asserts both the parsed `Field` values and the exact output bytes.
- Write fixtures as **bytes** (`Path.write_bytes` or `b"..."` literals) so editors and git
  can't normalize line endings or encoding. Add a `.gitattributes` entry
  `tests/fixtures/** -text` to stop git's CRLF conversion on Windows.
- Required fixtures, at minimum: CRLF, LF, mixed endings, bare `\r`, quoted commas,
  doubled quotes, embedded LF and CRLF, empty file, headers only, UTF-8 multilingual,
  UTF-8 with BOM, cp1252, Latin-1, UTF-16 with BOM, leading-zero IDs and coordinates,
  trailing delimiter (every row and only some rows), whitespace around delimiters,
  unclosed quote, junk after a closing quote, short and long ragged rows, NULL vs `""`,
  semicolon and tab delimiters, and an ambiguous-delimiter file.
- Error tests assert the reported line/column, not just that an error happened.
- Run tests with: `python -m pytest` from the `CSV Cleaner` folder.

## When changing behavior

If a change affects any rule above, update this file **in the same change** and add or
adjust the matching fixture. The rules table is the spec.
