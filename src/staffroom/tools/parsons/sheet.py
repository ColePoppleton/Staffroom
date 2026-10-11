"""Turn a Problem into a house-style Document (sheet + key)."""

from __future__ import annotations

from datetime import date

from staffroom.core.export import (
    AnswerGrid,
    BoxedBlocks,
    Code,
    Document,
    HintBox,
    Paragraph,
    TableBlock,
    sheet_date,
)
from staffroom.tools.parsons.logic import (
    Block,
    Options,
    Problem,
    reconstruct,
    render_block,
)


def build_document(
    problem: Problem, name: str, options: Options, today: date | None = None
) -> Document:
    doc = Document(
        title=f"Parsons problem: {name}",
        topic="Python",
        date=today or sheet_date(),
        subtitle=(
            f"seed {problem.seed} · {problem.granularity} blocks · {len(problem.solution)} needed"
        ),
    )
    sheet = doc.section()
    sheet.add(
        Paragraph(
            "Put the blocks in the right order to make a working program: cut them out "
            "along the dashed lines, or write their numbers in the grid. "
            + (
                "Some blocks are wrong and must be left out. "
                if problem.distractor_numbers()
                else ""
            )
            + (
                ""
                if options.show_indentation
                else "Indentation has been removed: decide it yourself. "
            ),
            style="instruction",
        )
    )
    if options.hint:
        sheet.add(
            HintBox(
                "Start by finding the first line that must run. Look for lines that set up "
                "variables before they are used, and for headers that end in a colon."
            )
        )
    sheet.add(
        BoxedBlocks(
            tuple(render_block(b, options.show_indentation) for b in problem.shuffled),
            columns=2,
        )
    )
    sheet.add(Paragraph("Write the block numbers in order:", style="instruction"))
    sheet.add(AnswerGrid(len(problem.solution)))

    key = doc.section("Answer key", answers=True)
    key.add(Paragraph("Correct order: " + ", ".join(str(n) for n in problem.answer_order())))
    if problem.distractor_numbers():
        key.add(
            Paragraph(
                "Distractors (leave out): "
                + ", ".join(str(n) for n in problem.distractor_numbers())
            )
        )
        key.add(
            TableBlock(
                ("Block", "Distractor", "Looks like"),
                tuple(
                    (str(n), b.lines[0], _closest(b, problem))
                    for n, b in problem.numbered()
                    if b.distractor
                ),
                monospace=True,
            )
        )
    key.add(Code(reconstruct(problem.solution), caption="Reconstructed program"))
    return doc


def _closest(distractor: Block, problem: Problem) -> str:
    first = distractor.lines[0]
    best = max(problem.solution, key=lambda b: _overlap(b.lines[0], first))
    return best.lines[0]


def _overlap(a: str, b: str) -> int:
    return sum(1 for x, y in zip(a, b, strict=False) if x == y)
