# Worksheet

Seeded sets of theory questions with answer keys. The seed, difficulty and
count are printed in the header so a set can be regenerated. A count outside
1–60 is refused with a sentence rather than writing an empty sheet.

![Worksheet panel](../worksheet-light.png)

## Topics

| Topic | What it asks |
| --- | --- |
| binary | denary ↔ binary ↔ hex (4, 8 or 12 bits by difficulty) |
| twos_complement | 8-bit two's complement both ways |
| binary_addition | 8-bit addition with the overflow flag |
| shifts | logical and arithmetic shifts and their effect |
| truth_tables | 2 or 3 inputs; the gates follow the board and level (below) |
| boolean_simplification | with each law written in the question's own letters in the key |
| file_size | image, sound and text calculations |
| rle | run-length encode and decode |
| huffman | total bits for a small frequency table |

Every generator is verified in the tests by independent computation.

## Logic questions

Truth tables use the gates the exam board requires: OCR J277 is AND, OR and
NOT; AQA 8525 adds XOR. Neither GCSE board has NAND or NOR, so those appear
only when **Level** is *A level* (`--level a_level`) *and* **Difficulty** is
*Hard* (A-level also
adds XOR at every difficulty). The board comes from Settings (`general.board`)
or `--board`. Every question uses all of the inputs its table lists, no gate is
fed the same input twice, and Q is never constant or simply one input. Each
difficulty has its own shape: easy is one gate on two inputs, medium two gates
(`(A AND B) OR NOT C`), hard three gates or a NOT over a bracket
(`NOT (A OR B) AND (C AND NOT B)`).

Boolean simplification builds each question from textbook forms: a law wraps
one letter (or `NOT` letter), or one small gate, in its longer form —
absorption `A OR (A AND C)`, the distributive pair `(A AND B) OR (A AND NOT B)`,
the redundancy form `A AND (NOT A OR B)`, De Morgan `NOT (NOT A OR NOT B)` —
and the key undoes the wraps in order, each step in the question's own letters:
`absorption: B AND (B OR NOT C) = B, leaving A AND B`. Easy is one step, medium
two, hard three, and a question stays the size of an exam one at every
difficulty (a hard sheet reads `(A OR (A AND C)) AND NOT (A AND NOT B)`, not a
form nested inside a form inside a form); a sheet never repeats a question.
**Boolean laws** chooses what is practised: *Absorption* (`absorption`:
absorption, distributive and complement; the default), *Absorption + De
Morgan* (`de_morgan`), *Identities* (`identities`: identity, idempotent,
double negation, complement; the only family that puts `X AND X`, `NOT NOT
X` or `0`/`1` on the sheet) or *All laws* (`all`). The panel shows **Level**
only for truth tables and **Boolean laws** only for Boolean simplification.

The header names the gate set or the law family next to the seed, so a sheet
describes the settings that regenerate it; an A-level sheet also gets `alevel`
in its file name so it never overwrites the GCSE sheet with the same seed.

![A hard truth-table sheet for OCR](../worksheet-sample.png)

```bash
staff worksheet make --topic binary --count 20 --seed 42 --difficulty medium
staff worksheet make --topic truth_tables --difficulty hard --level a_level --board aqa
staff worksheet make --topic boolean_simplification --laws de_morgan
staff worksheet topics
```

Output: `<topic>_<difficulty>_s<seed>.docx/.pdf` plus a `_key` file, in the
[house style](../guide/house-style.md), in `~/TeachingSessions/outputs/worksheet/`
unless Settings names an output folder ([Outputs](../guide/outputs.md)).
*Seed*, *level* and *Boolean laws* are in the [Glossary](../guide/glossary.md).
