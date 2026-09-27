"""End-to-end tests that run main.py as a real command."""

import subprocess
import sys
from pathlib import Path

import pytest

from build_fixtures import FIXTURES

MAIN = Path(__file__).parent.parent / "main.py"


def cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(MAIN), *map(str, args)], capture_output=True)


@pytest.fixture
def make_input(tmp_path):
    def make(name: str) -> Path:
        path = tmp_path / name
        path.write_bytes(FIXTURES[name])
        return path

    return make


def test_clean_file_exits_0_and_writes_output(make_input, tmp_path):
    out = tmp_path / "out.csv"
    result = cli(make_input("crlf.csv"), "-o", out)
    assert result.returncode == 0
    assert out.read_bytes() == b"a,b\r\n1,2\r\n3,4\r\n"
    assert b"encoding: utf-8" in result.stderr
    assert b"delimiter: comma (detected)" in result.stderr


def test_without_output_writes_to_stdout(make_input):
    result = cli(make_input("lf.csv"))
    assert result.returncode == 0
    assert result.stdout == b"a,b\r\n1,2\r\n3,4\r\n"


def test_warnings_exit_1_and_go_to_stderr_only(make_input):
    result = cli(make_input("bare_cr.csv"))
    assert result.returncode == 1
    assert b"warning: line 2, col 2: bare carriage return" in result.stderr
    assert b"warning" not in result.stdout


def test_fatal_error_exits_2_and_writes_nothing(make_input, tmp_path):
    out = tmp_path / "out.csv"
    result = cli(make_input("unclosed_quote.csv"), "-o", out)
    assert result.returncode == 2
    assert b"error: line 3, col 3: quoted field is never closed" in result.stderr
    assert not out.exists()
    assert list(tmp_path.iterdir()) == [tmp_path / "unclosed_quote.csv"]


def test_fatal_error_leaves_existing_output_untouched(make_input, tmp_path):
    out = tmp_path / "out.csv"
    out.write_bytes(b"previous run\r\n")
    assert cli(make_input("junk_after_quote.csv"), "-o", out).returncode == 2
    assert out.read_bytes() == b"previous run\r\n"


def test_rejects_file_is_named_after_output(make_input, tmp_path):
    out = tmp_path / "clean.csv"
    result = cli(make_input("ragged.csv"), "-o", out)
    assert result.returncode == 1
    rejects = tmp_path / "clean.rejects.csv"
    assert rejects.read_bytes().startswith(b"line,reason,raw_row\r\n2,")
    assert b"rejected rows written to" in result.stderr


def test_rejects_file_is_named_after_input_when_writing_to_stdout(make_input, tmp_path):
    assert cli(make_input("ragged.csv")).returncode == 1
    assert (tmp_path / "ragged.rejects.csv").exists()


def test_no_rejects_file_when_nothing_is_rejected(make_input, tmp_path):
    cli(make_input("crlf.csv"), "-o", tmp_path / "out.csv")
    assert not list(tmp_path.glob("*.rejects.csv"))


def test_no_temp_files_are_left_behind(make_input, tmp_path):
    cli(make_input("ragged.csv"), "-o", tmp_path / "out.csv")
    assert not list(tmp_path.glob("*.tmp"))


def test_output_can_overwrite_the_input(make_input):
    path = make_input("whitespace.csv")
    assert cli(path, "-o", path).returncode == 0
    assert path.read_bytes() == b'a,b,c\r\n"  x "," y ","  z  "\r\n'


@pytest.mark.parametrize("spelling", ["\\t", "tab", "\t"])
def test_tab_delimiter_spellings(make_input, spelling):
    result = cli(make_input("tab.csv"), "--delimiter", spelling)
    assert result.returncode == 0
    assert result.stdout.startswith(b"id,name,note\r\n")


def test_all_flags(make_input):
    result = cli(
        make_input("ragged.csv"), "--delimiter", ",", "--out-delimiter", "|", "--encoding", "utf-8",
        "--lf", "--bom", "--strip", "--pad-short",
    )
    assert result.returncode == 1
    assert result.stdout == b"\xef\xbb\xbfa|b|c\n1|2|\n5|6|7\n"


def test_unknown_flag_exits_2(make_input):
    assert cli(make_input("crlf.csv"), "--dedupe").returncode == 2


def test_missing_input_exits_2(tmp_path):
    result = cli(tmp_path / "nope.csv")
    assert result.returncode == 2
    assert b"error: cannot read" in result.stderr


def test_ambiguous_delimiter_asks_for_the_flag(make_input):
    result = cli(make_input("ambiguous_delimiter.csv"))
    assert result.returncode == 2
    assert b"pass --delimiter" in result.stderr
