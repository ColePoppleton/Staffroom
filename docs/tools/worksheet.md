# Worksheet

Seeded sets of theory questions with answer keys. The seed, difficulty and
count are printed in the header so a set can be regenerated.

![Worksheet panel](../worksheet-light.png)

## Topics

| Topic | What it asks |
| --- | --- |
| binary | denary ↔ binary ↔ hex (4, 8 or 12 bits by difficulty) |
| twos_complement | 8-bit two's complement both ways |
| binary_addition | 8-bit addition with the overflow flag |
| shifts | logical and arithmetic shifts and their effect |
| truth_tables | 2 or 3 inputs, AND/OR/XOR/NAND/NOR/NOT |
| boolean_simplification | with the laws listed step by step in the key |
| file_size | image, sound and text calculations |
| rle | run-length encode and decode |
| huffman | total bits for a small frequency table |

Every generator is verified in the tests by independent computation.

```bash
tt worksheet make --topic binary --count 20 --seed 42 --difficulty medium
tt worksheet topics
```

Output: `<topic>_<difficulty>_s<seed>.docx/.pdf` plus a `_key` file, in the
[house style](../guide/house-style.md).
