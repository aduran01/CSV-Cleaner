# CSV Cleaner — Repository Rules

**`SPEC.md` is the source of truth** for what this project does: the problem, non-goals,
constraints, affected files, and acceptance criteria. This file covers *how* to work in
the repo. Read `SPEC.md` before making changes, and don't build anything listed under its
non-goals.

## Implementation approach

- The parser is a hand-written character-by-character state machine, with states such as
  `FIELD_START`, `UNQUOTED`, `QUOTED`, and `QUOTE_IN_QUOTED`.
- The parser returns rows of `Field` objects that record at least `value: str`,
  `quoted: bool`, and the source line and column, for error messages.
- Read input as **bytes** and decode it in `encoding.py`. Don't open input in text mode,
  because that lets Python translate newlines.
- Write output as bytes too, for the same reason.
- To avoid leaving partial output after a fatal error, finish parsing before writing
  anything. Alternatively, write to a temporary file and rename it at the end.

## Testing practice

- Create fixtures as **bytes**, using `Path.write_bytes` or `b"..."` literals, so editors
  and git can't change line endings or encoding.
- `.gitattributes` must contain `tests/fixtures/** -text`, which turns off git's CRLF
  conversion on Windows.
- Name each fixture after the case it covers, e.g. `bare_cr.csv` or `utf16_bom.csv`.
- Run the tests with `python -m pytest` from the `CSV Cleaner` folder.

## Changing behavior

A change to behavior means updating the matching acceptance criterion in `SPEC.md`, and its
fixture and test, **in the same change**. If a request would need something listed under
the non-goals, point that out and ask before building it.
