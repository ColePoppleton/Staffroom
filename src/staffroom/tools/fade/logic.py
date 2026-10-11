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
            "help": "Which lines are blanked first, or only the lines you list",
        },
    )
    ranges: str = field(
        default="",
        metadata={"label": "Line ranges", "help": "e.g. 3-5, 8: the lines to blank, in order"},
    )
    keep_headers: bool = field(
        default=True,
        metadata={"label": "Keep headers", "help": "Never blank def / if / for / while lines"},
    )
    formats: Literal["both", "docx", "pdf"] = field(default="both", metadata={"label": "Output"})


RANGES_HINT = "Line ranges like 3-5, 8"


def parse_ranges(text: str) -> list[int]:
    """``"3-5, 8"`` -> [3, 4, 5, 8]. Raises ValueError saying what was expected."""
    out: list[int] = []
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                lo, hi = int(a), int(b)
                out.extend(range(min(lo, hi), max(lo, hi) + 1))
            else:
                out.append(int(part))
        except ValueError:
            msg = f"{RANGES_HINT} (line numbers), not {part!r}."
            raise ValueError(msg) from None
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


def _code_lines(source: str, options: Options) -> list[int]:
    """1-based numbers of the lines that may be blanked, in file order."""
    lines = source.splitlines()
    code = [i + 1 for i, ln in enumerate(lines) if ln.strip() and not ln.lstrip().startswith("#")]
    if options.keep_headers:
        headers = header_lines(source)
        code = [n for n in code if n not in headers]
    return code


def fadeable_lines(source: str, options: Options) -> list[int]:
    """1-based line numbers in the order they get blanked."""
    code = _code_lines(source, options)
    if options.order == "ranges":
        wanted = parse_ranges(options.ranges)
        return [n for n in wanted if n in code]
    if options.order == "top_down":
        return code
    return list(reversed(code))


def _lines_phrase(numbers: list[int]) -> str:
    """[10, 11, 12] -> "Lines 10-12"; [4] -> "Line 4"; [2, 5] -> "Lines 2, 5"."""
    if len(numbers) == 1:
        return f"Line {numbers[0]}"
    if numbers == list(range(numbers[0], numbers[-1] + 1)):
        return f"Lines {numbers[0]}-{numbers[-1]}"
    return "Lines " + ", ".join(str(n) for n in numbers)


def unfadeable_lines(source: str, options: Options) -> list[tuple[int, str]]:
    """For ``order == "ranges"``: the listed lines that will not be blanked and
    why, as ``(line, reason)``. Empty for the other orders."""
    if options.order != "ranges":
        return []
    lines = source.splitlines()
    code = set(_code_lines(source, options))
    headers = header_lines(source) if options.keep_headers else set()
    out: list[tuple[int, str]] = []
    for n in parse_ranges(options.ranges):
        if n in code or not 1 <= n <= len(lines):
            continue  # out-of-file lines are an error in fade_versions, not a skip
        if not lines[n - 1].strip():
            out.append((n, f"line {n} is blank"))
        elif lines[n - 1].lstrip().startswith("#"):
            out.append((n, f"line {n} is a comment"))
        elif n in headers:
            out.append((n, f"line {n} is a def/if/for/while header (Keep headers is on)"))
    return out


def _check_ranges(source: str, options: Options) -> None:
    """Raise ValueError for range mistakes a teacher would want told about."""
    if options.order != "ranges":
        if options.ranges.strip():
            msg = (
                f"Line ranges are listed but Fade order is '{options.order}'. "
                "Choose 'ranges' to fade only those lines, or clear the ranges."
            )
            raise ValueError(msg)
        return
    if not options.ranges.strip():
        msg = f"Fade order is 'ranges' but no lines are listed. {RANGES_HINT}."
        raise ValueError(msg)
    wanted = parse_ranges(options.ranges)
    total = len(source.splitlines())
    too_small = [n for n in wanted if n < 1]
    if too_small:
        msg = f"{_lines_phrase(too_small)} cannot fade: line numbers start at 1."
        raise ValueError(msg)
    too_big = [n for n in wanted if n > total]
    if too_big:
        verb = "is" if len(too_big) == 1 else "are"
        msg = f"{_lines_phrase(too_big)} {verb} past the end of the file ({total} lines)."
        raise ValueError(msg)


def blank_line(line: str) -> str:
    indent = len(line) - len(line.lstrip(" "))
    return " " * indent + BLANK


def fade_versions(source: str, options: Options) -> list[str]:
    """Version j of K blanks the first round(j * n / K) lines of the fade
    order, so the last version has every chosen line blanked.

    K is capped at n, the number of lines that can fade, so every version has
    at least one blank and strictly more than the version before it. Callers
    compare ``len(result)`` with ``options.steps`` to tell the teacher.

    Raises SyntaxError when ``source`` is not Python, ValueError (with a message
    for the teacher) when the settings leave nothing to fade."""
    ast.parse(source)
    _check_ranges(source, options)
    order = fadeable_lines(source, options)
    n = len(order)
    if n == 0:
        if options.order == "ranges":
            reasons = "; ".join(why for _n, why in unfadeable_lines(source, options))
            msg = f"Nothing to fade: {reasons}."
        else:
            msg = (
                "Nothing to fade: every line is a header, a comment or blank. "
                "Untick Keep headers or add more code."
            )
        raise ValueError(msg)
    steps = min(options.steps, n)
    lines = source.splitlines()
    versions: list[str] = []
    for j in range(1, steps + 1):
        how_many = round(j * n / steps)
        blanked = set(order[:how_many])
        text = [blank_line(ln) if i + 1 in blanked else ln for i, ln in enumerate(lines)]
        versions.append("\n".join(text) + "\n")
    return versions


def blank_count(version: str) -> int:
    return sum(1 for ln in version.splitlines() if ln.strip() == BLANK)
