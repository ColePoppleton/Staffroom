"""Pure logic for fade: progressively blank out lines of a worked solution."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Literal

BLANK = "________"
Order = Literal["bottom_up", "top_down", "ranges"]


@dataclass
class Options:
    steps: int = field(default=4, metadata={"label": "Versions", "min": 1, "max": 12})
    order: Order = field(
        default="bottom_up",
        metadata={
            "label": "Fade order",
            "help": "bottom_up: last lines go first; ranges: only the lines listed",
        },
    )
    ranges: str = field(
        default="",
        metadata={"label": "Line ranges", "help": "e.g. 3-5, 8 (used when order is ranges)"},
    )
    keep_headers: bool = field(
        default=True,
        metadata={"label": "Keep headers", "help": "Never blank def / if / for / while lines"},
    )
    formats: Literal["both", "docx", "pdf"] = field(default="both", metadata={"label": "Output"})


def parse_ranges(text: str) -> list[int]:
    """``"3-5, 8"`` -> [3, 4, 5, 8]."""
    out: list[int] = []
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            lo, hi = int(a), int(b)
            out.extend(range(min(lo, hi), max(lo, hi) + 1))
        else:
            out.append(int(part))
    seen: dict[int, None] = {}
    for n in out:
        seen.setdefault(n, None)
    return list(seen)


def header_lines(source: str) -> set[int]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    headers: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, ast.If | ast.For | ast.While | ast.FunctionDef | ast.With | ast.Try | ast.ClassDef
        ):
            headers.add(node.lineno)
            for attr in ("orelse", "finalbody"):
                body = getattr(node, attr, None)
                if body:
                    headers.add(body[0].lineno - 1)
            for h in getattr(node, "handlers", []) or []:
                headers.add(h.lineno)
    return headers


def fadeable_lines(source: str, options: Options) -> list[int]:
    """1-based line numbers in the order they get blanked."""
    lines = source.splitlines()
    code = [i + 1 for i, ln in enumerate(lines) if ln.strip() and not ln.lstrip().startswith("#")]
    if options.keep_headers:
        headers = header_lines(source)
        code = [n for n in code if n not in headers]
    if options.order == "ranges":
        wanted = parse_ranges(options.ranges)
        return [n for n in wanted if n in code]
    if options.order == "top_down":
        return code
    return list(reversed(code))


def blank_line(line: str) -> str:
    indent = len(line) - len(line.lstrip(" "))
    return " " * indent + BLANK


def fade_versions(source: str, options: Options) -> list[str]:
    """Version j of K blanks the first round(j * n / K) lines of the fade
    order, so the last version has every chosen line blanked."""
    order = fadeable_lines(source, options)
    n = len(order)
    if n == 0:
        msg = "Nothing to fade: no code lines match the settings."
        raise ValueError(msg)
    lines = source.splitlines()
    versions: list[str] = []
    for j in range(1, options.steps + 1):
        how_many = round(j * n / options.steps)
        blanked = set(order[:how_many])
        text = [blank_line(ln) if i + 1 in blanked else ln for i, ln in enumerate(lines)]
        versions.append("\n".join(text) + "\n")
    return versions


def blank_count(version: str) -> int:
    return sum(1 for ln in version.splitlines() if ln.strip() == BLANK)
