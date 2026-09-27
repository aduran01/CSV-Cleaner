"""Write every fixture in tests/fixtures/ from byte literals.

Run `py tests/build_fixtures.py` after adding or changing a fixture. The bytes
live here, so an editor or git can never change them.
"""

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"

FIXTURES: dict[str, bytes] = {
    # Encoding
    "empty.csv": b"",
    "utf8_multilingual.csv": "name,city\r\nJosé,São Paulo\r\n李雷,北京\r\n"
    "שלום,תל אביב\r\nparty,\U0001f389\r\n".encode("utf-8"),
    "utf8_bom.csv": b"\xef\xbb\xbfid,name\r\n1,Zo\xc3\xab\r\n",
    "utf16le_bom.csv": "﻿id,name\r\n1,Zoë\r\n".encode("utf-16-le"),
    "utf16be_bom.csv": "﻿id,name\r\n1,Zoë\r\n".encode("utf-16-be"),
    "utf32le_bom.csv": "﻿id,name\r\n1,Zoë\r\n".encode("utf-32-le"),
    # 0x80 is the euro sign in cp1252; 0xE9 is e-acute.
    "cp1252.csv": b"item,price\r\ncaf\xe9,\x805\r\n",
    # 0x81 is undefined in cp1252, so this can only be Latin-1.
    "latin1.csv": b"code,label\r\n\x81,na\xefve\r\n",
    # Line endings
    "crlf.csv": b"a,b\r\n1,2\r\n3,4\r\n",
    "lf.csv": b"a,b\n1,2\n3,4\n",
    "mixed_endings.csv": b"a,b\r\n1,2\n3,4\r\n",
    "no_final_newline.csv": b"a,b\r\n1,2",
    "bare_cr.csv": b"a,b\r\nx\ry,2\r\n",
    # Quoting
    "quoted_commas.csv": b'name,address\r\nAda,"12 Main St, Apt 4"\r\n',
    "doubled_quotes.csv": b'id,quote\r\n1,"She said ""hi"""\r\n2,""""\r\n',
    "embedded_lf.csv": b'id,note\r\n1,"line one\nline two"\r\n2,x\r\n',
    "embedded_crlf.csv": b'id,note\r\n1,"line one\r\nline two"\r\n2,x\r\n',
    "mid_field_quote.csv": b'a,b\r\n5\'10",x\r\n1, "q"\r\n',
    "unclosed_quote.csv": b'a,b\r\n1,2\r\n3,"never closed\r\n4,5\r\n',
    "junk_after_quote.csv": b'a,b\r\n"abc"x,1\r\n',
    # Whitespace
    "whitespace.csv": b'a,b,c\r\n  x , y ,"  z  "\r\n',
    # NULL vs. empty string
    "null_vs_empty.csv": b'a,b,c\r\n1,,""\r\n,"",\r\n',
    # Empty and minimal files
    "headers_only.csv": b"id,name,zip\r\n",
    "blank_lines.csv": b"a,b\r\n\r\n1,2\n\n3,4\r\n",
    # Delimiter detection
    "semicolon_decimal_comma.csv": b"item;price;weight\r\napple;3,14;0,5\r\npear;2,50;1,25\r\n",
    "tab.csv": b"id\tname\tnote\r\n1\tAda\thello, world\r\n2\tBob\tx\r\n",
    "pipe.csv": b"id|name\r\n1|Ada\r\n2|Bob\r\n",
    # Counting commas without respecting quotes would pick comma (3 per row).
    "quoted_delimiters.csv": b'"x,y,z";b\r\n"1,2,3";4\r\n',
    # With comma, the quotes land mid-field, so comma splits 2 per row too. Only its
    # quote warnings separate it from semicolon.
    "quotes_break_tie.csv": b'a;"x,y"\r\n1;"p,q"\r\n',
    "ambiguous_delimiter.csv": b"a,b|c\r\n1,2|3\r\n",
    "single_column.csv": b"name\r\nAda\r\nBob\r\n",
    # Values that must never change
    "numeric_looking.csv": b"zip,lat,lon,id,sci,nan,flag,date\r\n"
    b"00501,40.7128,-74.0060,000123456789012345,1e5,NaN,TRUE,03/04/2025\r\n"
    b"007,-0.0,0.10,42,1E-3,nan,false,2025-04-03\r\n",
}


def build() -> None:
    FIXTURES_DIR.mkdir(exist_ok=True)
    for name, data in FIXTURES.items():
        (FIXTURES_DIR / name).write_bytes(data)


if __name__ == "__main__":
    build()
    print(f"wrote {len(FIXTURES)} fixtures to {FIXTURES_DIR}")
