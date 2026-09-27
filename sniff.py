"""Detect the delimiter by parsing a sample of rows with each candidate."""

from collections import Counter
from itertools import islice

from diagnostics import CleanerError, Reporter
from parser import parse

CANDIDATES = (",", ";", "\t", "|")
NAMES = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}
SAMPLE_ROWS = 50


def detect_delimiter(text: str, reporter: Reporter) -> str:
    """Return the candidate that splits the sample most consistently.

    A candidate's score is how many sample rows share its most common field
    count, which must be greater than 1. Ties go to the candidate with fewer
    parser warnings, since a wrong delimiter tends to leave quotes in the
    middle of unquoted fields. If candidates are still tied, the file is ambiguous
    and the user must pass --delimiter.
    """
    ranked = []  # (score, -warnings, delimiter)
    failures = []
    for delimiter in CANDIDATES:
        scratch = Reporter()  # the sample parse's warnings are only used for ranking
        try:
            rows = list(islice(parse(text, delimiter, scratch), SAMPLE_ROWS))
        except CleanerError as exc:
            failures.append(f"{NAMES[delimiter]}: {exc.diagnostic.format()}")
            continue
        counts = Counter(len(row.fields) for row in rows)
        if not counts:
            continue
        field_count, score = counts.most_common(1)[0]
        if field_count > 1:
            ranked.append((score, -len(scratch.warnings), delimiter))

    if not ranked:
        if failures:
            raise CleanerError(
                "could not detect the delimiter; pass --delimiter ("
                + "; ".join(failures)
                + ")"
            )
        # No candidate appears outside quotes, so every choice parses the same way.
        reporter.info("delimiter: comma (single column, no delimiter found)")
        return ","

    # Stable sort on the rank only, so tied candidates stay in CANDIDATES order.
    ranked.sort(key=lambda r: r[:2], reverse=True)
    best = ranked[0]
    if len(ranked) > 1 and ranked[1][:2] == best[:2]:
        tied = " and ".join(NAMES[r[2]] for r in ranked if r[:2] == best[:2])
        raise CleanerError(f"could not detect the delimiter: {tied} fit equally well; pass --delimiter")
    reporter.info(f"delimiter: {NAMES[best[2]]} (detected)")
    return best[2]
