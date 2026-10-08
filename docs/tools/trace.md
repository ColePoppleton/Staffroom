# Trace

Runs a program step by step in a sandbox and produces a blank trace table
for pupils and a completed one for you.

![Trace panel](../trace-dark.png)

Each row is one executed line with every variable's value **after** that
line and anything it printed. Choose which lines to record (assignments,
loop headers, ifs, calls) and which variables to show. Programs that read
input take it from the *Inputs* box, one line per `input()`.

The sandbox is a subprocess with a hard timeout, a temp working folder and
no network; an infinite loop is killed and reported.

```bash
staff trace make program.py --stdin "5\n3" --steps 60 --vars total,count
```
