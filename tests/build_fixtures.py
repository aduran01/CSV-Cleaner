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
}


def build() -> None:
    FIXTURES_DIR.mkdir(exist_ok=True)
    for name, data in FIXTURES.items():
        (FIXTURES_DIR / name).write_bytes(data)


if __name__ == "__main__":
    build()
    print(f"wrote {len(FIXTURES)} fixtures to {FIXTURES_DIR}")
