"""Compact terminal identity for the existing ``ultra`` command."""
from __future__ import annotations

import os
import shutil
import sys
import textwrap
from typing import TextIO

TITLE = "YOUTUBE EDIT ULTRA"

_RED = "\033[91m"
_WHITE = "\033[1;97m"
_FRAME = "\033[2;37m"
_RESET = "\033[0m"


def should_show_banner() -> bool:
    """Keep automatic decoration out of pipelines, redirected output and CI."""
    return not os.environ.get("CI") and all(
        stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)
    )


def print_banner(stream: TextIO | None = None) -> None:
    """Print the identity explicitly, using color only on a capable terminal."""
    if stream is None:
        stream = sys.stdout
    width = max(1, min(80, shutil.get_terminal_size(fallback=(80, 24)).columns))
    dumb = os.environ.get("TERM") == "dumb"
    color = stream.isatty() and not dumb and "NO_COLOR" not in os.environ
    try:
        "▶╭─╮│╰╯".encode(stream.encoding or "utf-8")
        unicode = True
    except (UnicodeEncodeError, LookupError):
        unicode = False
    play = "▶" if unicode else ">"

    def paint(text: str, style: str) -> str:
        return f"{style}{text}{_RESET}" if color else text

    if width < 32 or dumb:
        lines = textwrap.wrap(f"{play} {TITLE}", width=width)
        if color:
            lines = [
                _WHITE + line.replace(play, _RED + play + _WHITE, 1) + _RESET
                for line in lines
            ]
    else:
        left_top, horizontal, right_top, vertical, left_bottom, right_bottom = (
            ("╭", "─", "╮", "│", "╰", "╯") if unicode else ("+", "-", "+", "|", "+", "+")
        )
        first, second = TITLE.split(" ", 1)
        border = paint(vertical, _FRAME)
        lines = [
            paint(left_top + horizontal * 30 + right_top, _FRAME),
            border + "  " + paint(play, _RED) + "   " + paint(first, _WHITE)
            + " " * (24 - len(first)) + border,
            border + "      " + paint(second, _WHITE) + " " * (24 - len(second)) + border,
            paint(left_bottom + horizontal * 30 + right_bottom, _FRAME),
        ]
    print("\n".join(lines), file=stream)
