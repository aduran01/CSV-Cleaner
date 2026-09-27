"""Warnings and errors collected while cleaning, reported on stderr by main.py."""

import sys
from dataclasses import dataclass
from typing import TextIO


@dataclass(frozen=True)
class Diagnostic:
    level: str  # "info", "warning", or "error"
    message: str
    line: int | None = None
    column: int | None = None

    def format(self) -> str:
        where = f"line {self.line}, col {self.column}: " if self.line is not None else ""
        return f"{self.level}: {where}{self.message}"


class CleanerError(Exception):
    """A fatal problem. Nothing is written and the exit code is 2."""

    def __init__(self, message: str, line: int | None = None, column: int | None = None):
        super().__init__(message)
        self.diagnostic = Diagnostic("error", message, line, column)


class Reporter:
    """Collects diagnostics so tests can inspect them and main.py can print them."""

    def __init__(self) -> None:
        self.diagnostics: list[Diagnostic] = []

    def info(self, message: str) -> None:
        self.diagnostics.append(Diagnostic("info", message))

    def warn(self, message: str, line: int, column: int) -> None:
        self.diagnostics.append(Diagnostic("warning", message, line, column))

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.level == "warning"]

    def flush(self, stream: TextIO = sys.stderr) -> None:
        for diagnostic in self.diagnostics:
            print(diagnostic.format(), file=stream)
        self.diagnostics.clear()
