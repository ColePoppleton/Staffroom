# Bugs

Inject one controlled error per copy of a working program. Pupils find the
line and predict what happens; the key knows, because each variant was run.

![Bugs panel](../bugs-light.png)

Error classes: comparison flipped, off by one, missing colon, missing
bracket, wrong variable name, indentation slip, string / integer confusion.
Each variant differs from the original by exactly one line, and the key says
*crashes: SyntaxError*, *runs, but the output is wrong*, *hangs*, or
*no visible change*.

```bash
staff bugs make program.py -n 4 --seed 1 --kinds missing_colon,off_by_one --stdin "Apple"
staff bugs kinds
```
