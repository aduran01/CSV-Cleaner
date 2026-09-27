# CSV Cleaner

The CSV Cleaner is a command-line tool that takes a messy, real-world CSV file and produces a clean, consistent, RFC 4180–style CSV. It does this without silently changing any of the data inside it. It was built from a written spec and repository rules first, and then one module at a time, with every major piece reviewed before the next one began. This document explains the problem the project set out to solve and how the work was organized. It also covers the struggles along the way, the reasons behind the tech stack, the decisions and tradeoffs that shaped the code, and what the finished tool delivers.

## Usage

```
py main.py INPUT [-o OUTPUT] [--delimiter D] [--out-delimiter D] [--encoding NAME]
                 [--lf] [--bom] [--strip] [--pad-short]
```

The cleaned file is written to `OUTPUT`, or to stdout if no output file is given. Every successful run also writes a rejects file next to it (`<name>.rejects.csv`) that lists any rows that could not be kept, along with the reason and the row's original text. Warnings and errors are printed to stderr with the line and column they refer to. The exit code is `0` for a clean run, `1` for a run that finished with warnings, and `2` for a fatal error, in which case nothing is written at all. A tab delimiter can be passed as `\t` or `tab`.

To run the tests, set up the virtual environment once and then run pytest from this folder:

```
py -m venv venv
venv\Scripts\python -m pip install -r requirements-dev.txt
venv\Scripts\python -m pytest
```

## The problem we were solving

CSV looks like the simplest data format there is, but in practice it is one of the least consistent. RFC 4180 describes a format, yet the files that people actually work with come from Excel, databases, older systems, and one-off scripts, and each of these bends the rules in its own way. Line endings may be CRLF or LF, or a mix of both. The delimiter may be a comma, or a semicolon in regions where the comma is used as a decimal separator. The file may be UTF-8, Windows-1252, or Latin-1, and nothing in the file itself says which. Most parsers deal with this by quietly guessing, and different parsers guess differently, which means that the same file can load as different data depending on the tool that opens it.

The goal of this project was to handle fifteen specific cases that make CSV difficult, many of which include:

- **Quoting:** commas and embedded newlines inside quoted fields, doubled quotes, and unclosed or malformed quotes.
- **Row endings and shape:** the bare carriage return, trailing delimiters, and ragged rows that have too few or too many fields.
- **Meaning:** the ambiguity between an intentional NULL and an empty string, and values such as zip codes or coordinates that look numeric but must never be converted.
- **Detection:** working out the file's delimiter and encoding, which the file never states.

Some of these cases have a clear answer in the RFC. Others, like the bare carriage return, are a genuine fork where well-known parsers disagree with one another, so the cleaner could not simply inherit whatever its language runtime happened to do. The central principle of the project therefore became that **the cleaner never silently changes data**. Every ambiguous situation is decided explicitly in writing. When a file cannot be read unambiguously, the cleaner reports exactly where the problem is instead of guessing.

## How the work was organized

Before any code was written, the project began with a set of repository rules in `CLAUDE.md`, which laid out the preliminary decisions for each of the base and edge cases along with general conventions for the code, the tech stack, and usage. These rules were then split into two documents with separate jobs. `SPEC.md` became the source of truth for what the tool does. It holds the problem statement, the constraints, the affected files, the acceptance criteria, and a list of non-goals. `CLAUDE.md` was reduced to how to work in the repository: how the parser is built, how the tests are written, and the rule that any change in behavior must update the spec at the same time.

The non-goals section turned out to be one of the most important parts of the spec. It lists what the cleaner deliberately does not do, such as type inference, deduplication, repairing broken quotes, or supporting other file formats. Without it, every "nice to have" idea would have been at risk of being treated as a requirement. Having it written down kept the scope narrow and made it easy to say no.

From there, the cleaner was built one module at a time. Each module arrived with its own tests and fixtures, and each was reviewed with an explanation of why it was built the way it was before the next one began. Moreover, whenever a module exposed a gap in the spec, the spec was updated in the same step, so the documents and the code never drifted apart.

## Why we chose this tech stack

The cleaner is written in **Python 3.10+ using only the standard library**, with pytest as the single dependency, and only for testing. This choice was deliberate, and several of the obvious alternatives were rejected for specific reasons.

The first alternative was Python's built-in `csv` module. On the surface it seems like the natural choice, but it conflicts with two of the project's core rules. It treats a bare carriage return as a line ending, while the spec requires it to be treated as data, as RFC-strict parsers do. It also throws away whether a field was quoted, which is exactly the information needed to tell NULL apart from an empty string. For these reasons the parser was written by hand as a character-by-character state machine, which keeps every one of these decisions under the project's control.

The second alternative was pandas. It is powerful, but its default behavior is to infer types, which is the very thing the cleaner must never do: a zip code like `00501` would silently become the number `501`. The third alternative was chardet for encoding detection. It was rejected because a fixed, predictable chain is enough for this project and is easier to explain. That chain checks for a byte-order mark first, then tries strict UTF-8, then Windows-1252, and finally Latin-1. Overall, staying within the standard library means the tool has no runtime dependencies to install. It also means that every behavior can be traced back to code in this folder rather than to a library's defaults.

## Architecture

The code is divided into small modules, each with one responsibility. This makes each rule easy to find and easy to test in isolation.

| Module | Responsibility |
|---|---|
| `diagnostics.py` | Collects warnings and errors with their line and column, and defines the fatal `CleanerError` |
| `encoding.py` | Detects the encoding from raw bytes, removes any byte-order mark, and decodes the text |
| `sniff.py` | Detects the delimiter by parsing a sample of rows with each candidate |
| `parser.py` | The state machine that turns text into rows of fields, recording whether each field was quoted |
| `clean.py` | Applies the rules that need the whole file: trailing delimiters, `--strip`, and row length |
| `writer.py` | Turns rows back into CSV text, deciding when a value needs quotes |
| `pipeline.py` | Runs every stage in order on the input bytes, with no file or console access |
| `main.py` | The command line: arguments, reading and writing files, and exit codes |

The parser only splits text into fields and never changes a value. The rules that alter the output, such as removing a trailing delimiter or trimming whitespace, live in `clean.py`. When a value looks wrong, this separation makes it clear which stage was responsible. Similarly, `pipeline.py` performs no file or console access, which allows the tests to exercise the entire cleaner directly without starting a new process each time.

## Decisions made

Several of the fifteen cases had no single correct answer, so each one required a decision that was then written into the spec and backed by a test.

- **Bare carriage return:** treated as literal field data, not as the end of a row, with a warning when it appears outside of quotes. This matches the RFC-strict parsers rather than Python's own behavior.
- **Whitespace around delimiters:** preserved by default, since the RFC counts it as part of the field. The optional `--strip` flag trims only spaces and tabs from unquoted fields, leaving other whitespace, like a non-breaking space, untouched.
- **Unclosed quotes and text after a closing quote:** treated as fatal errors that point to the exact line and column. The cleaner never guesses where a field was meant to end.
- **Trailing delimiters:** removed only when every row, header included, ends with one. When only some rows have one, those rows are treated as ragged instead.
- **Ragged rows:** not padded or cut down silently. They are moved to the rejects file with their original text and a reason. The `--pad-short` flag can fill short rows with NULL, but rows with too many fields are always rejected.
- **NULL versus empty string:** follows the PostgreSQL convention. An unquoted empty field is NULL and a quoted `""` is an empty string, and the output preserves this difference.
- **Numeric-looking values:** never converted. Leading zeros, coordinates, scientific notation, and dates in any format come out exactly as they went in.

On the other hand, some decisions only surfaced once the code was running, and they required judgment beyond the original spec. For instance, a single-column file contains no delimiter at all, so under the original wording delimiter detection would have treated a perfectly valid file as an error. Since every candidate parses such a file identically, it now safely defaults to a comma. Likewise, when two delimiter candidates split the sample equally well, the tie now goes to the one that produced fewer parser warnings, because a wrong delimiter tends to leave quotes stranded in the middle of fields. Finally, the rejects file is written on every successful run, even when it only contains a header. That way a rejects file left behind by an earlier run can never be mistaken for the current one.

## Struggles along the way

The most instructive struggle came from the idempotence tests, which check that cleaning the cleaned output a second time produces identical bytes. When the output delimiter was set to a semicolon, a value such as `x,y` was written without quotes, since it contained no semicolon. When that output was read again, the comma and the semicolon split every row in exactly the same way, and the cleaner correctly refused to guess between them. In other words, the cleaner was producing files that it could not read back without help. The fix was to quote any value that contains any of the delimiter candidates, not only the output delimiter. Only the real delimiter then ever appears outside quotes. This bug would have been very difficult to notice by hand, and it is the clearest example of why those tests were worth writing.

A related problem involved a row whose only field is NULL. Because NULL is written as nothing, such a row becomes an empty line, and an empty line is read back as a blank line and skipped, which means the row would disappear. CSV has no way to represent this case perfectly, so the cleaner writes it as an empty string and issues a warning, choosing a visible change over a silent loss. Furthermore, a small ordering bug in delimiter detection caused tied candidates to be listed in the wrong order in error messages, which the tests caught immediately.

Not every struggle was in the code itself. Getting the tests to appear in VS Code took some troubleshooting: the editor kept running test discovery with the system Python, which does not have pytest installed, instead of the project's virtual environment. The cause turned out to be a stray period at the end of the interpreter path, which prevented VS Code from recognizing the environment, so it quietly fell back to the system Python. Once the path was corrected, the tests were discovered as expected.

## Tradeoffs

Every decision in this project gave something up in exchange for predictability, and these tradeoffs were accepted deliberately.

- **Strictness over convenience:** a file with an unclosed quote stops the cleaner entirely, where a more forgiving tool might have produced some output. However, a forgiving tool would have had to guess, and a wrong guess can shift every value in the rows that follow.
- **Extra quoting:** quoting every delimiter candidate adds a few quotation marks that are not strictly necessary, such as `"3,50"` in a tab-delimited file. In exchange, the output is always unambiguous to read back.
- **The encoding fallback is still a judgment:** when a file is not valid UTF-8, it is read as Windows-1252, which is the most likely answer but not a certain one. The cleaner reports its choice so the user can override it with `--encoding`.
- **Whole-file processing:** reading the entire file into memory keeps the code simple and makes the trailing-delimiter rule possible, at the cost of performance on very large files, which was listed as a non-goal.
- **The rejects file is always written:** this prevents stale results, but it also means that writing to stdout still creates a file next to the input on every run.

## End result and impact

The finished cleaner handles every case it set out to cover, and it is verified by **231 automated tests** across **36 byte-exact fixture files**. The fixtures are generated from byte literals in a single script, so neither an editor nor git can rewrite their line endings or encoding. The tests check the parsed values, the exact output bytes, and the line and column of every warning and error. In addition, every fixture is cleaned twice under several combinations of options to confirm that the output never changes on a second pass.

The impact of the project is that a messy CSV file can now be turned into a predictable one without losing anything along the way. Leading zeros stay leading zeros, NULLs stay distinct from empty strings, and rows that cannot be kept are set aside with their original text rather than dropped. Every change the cleaner makes is reported with its location, and the exit codes allow the tool to be used safely inside scripts. Ultimately, the project showed that most of the difficulty in cleaning CSV is not in the parsing itself but in making each ambiguous decision explicit and keeping it consistent. Writing the spec before the code, and holding every module to it, is what made that possible.
