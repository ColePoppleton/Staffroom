# Trace

Runs a program step by step in a sandbox and produces a blank trace table
for pupils and a completed one for you.

![Trace panel](../trace-dark.png)

Each row is one executed line with every variable's value **after** that
line and anything it printed. Choose which lines to record (assignments,
loop headers, ifs, calls) and which variables to show. Programs that read
input take it from the *Inputs* box, one line per `input()`.

The program runs in a separate Python process with a 10 second limit, a
temporary working folder, a 1 MB cap on what it prints and a refusal to run
files that import networking modules. An infinite loop is killed and
reported; a print flood is cut at the cap and the key says so. This is not
a security sandbox: see [Running pupil code](../guide/running-code.md).

```bash
staff trace make program.py --stdin "5\n3" --steps 60 --vars total,count
```
