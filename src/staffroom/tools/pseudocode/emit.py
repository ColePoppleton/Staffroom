"""IR → text in one of three dialects: ``ocr`` (Exam Reference Language),
``aqa`` (AQA pseudocode) or ``python``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from staffroom.tools.pseudocode import ir

Dialect = Literal["ocr", "aqa", "python"]
INDENT = "    "

_PREC = {
    "OR": 1,
    "AND": 2,
    "NOT": 3,
    "==": 4,
    "!=": 4,
    "<": 4,
    "<=": 4,
    ">": 4,
    ">=": 4,
    "+": 5,
    "-": 5,
    "*": 6,
    "/": 6,
    "DIV": 6,
    "MOD": 6,
    "NEG": 7,
    "^": 8,
}


@dataclass
class EmitReport:
    notes: list[str] = field(default_factory=list)


class Emitter:
    def __init__(self, dialect: Dialect) -> None:
        self.d = dialect
        self.report = EmitReport()
        self.uses_random = False

    # -- program -------------------------------------------------------------
    def program(self, prog: ir.Program) -> str:
        lines = self.block(prog.body, 0)
        if (
            self.d == "python"
            and self.uses_random
            and not any(ln.strip() == "import random" for ln in lines)
        ):
            lines = ["import random", "", *lines]
        text = "\n".join(lines).rstrip("\n")
        return text + "\n" if text else ""

    def block(self, stmts: list[ir.Stmt], level: int) -> list[str]:
        if not stmts:
            return [INDENT * level + ("pass" if self.d == "python" else self.comment("nothing"))]
        out: list[str] = []
        for s in stmts:
            out += self.stmt(s, level)
        return out

    def comment(self, text: str) -> str:
        return ("// " if self.d == "ocr" else "# ") + text

    # -- statements ----------------------------------------------------------
    def stmt(self, s: ir.Stmt, level: int) -> list[str]:
        pad = INDENT * level
        if isinstance(s, ir.Comment):
            return [pad + self.comment(s.text)]
        if isinstance(s, ir.Untranslatable):
            return [pad + self.comment(f"could not translate: {s.source}")]
        if isinstance(s, ir.Pass):
            return [pad + ("pass" if self.d == "python" else self.comment("do nothing"))]
        if isinstance(s, ir.Assign):
            arrow = " ← " if self.d == "aqa" else " = "
            return [pad + self.expr(s.target) + arrow + self.expr(s.value)]
        if isinstance(s, ir.Output):
            args = ", ".join(self.expr(a) for a in s.args)
            if self.d == "aqa":
                return [pad + "OUTPUT " + args]
            return [pad + f"print({args})"]
        if isinstance(s, ir.ExprStmt):
            return [pad + self.expr(s.expr)]
        if isinstance(s, ir.ArrayDecl):
            if self.d == "ocr":
                return [pad + f"array {s.name}[{self.expr(s.size)}]"]
            if self.d == "aqa":
                self.report.notes.append(f"array {s.name} declared as a list of zeros")
                return [pad + f"{s.name} ← [0] * {self.expr(s.size)}"]
            return [pad + f"{s.name} = [0] * {self.expr(s.size)}"]
        if isinstance(s, ir.If):
            return self.if_(s, level)
        if isinstance(s, ir.While):
            test = self.expr(s.test)
            if self.d == "python":
                return [pad + f"while {test}:", *self.block(s.body, level + 1)]
            if self.d == "aqa":
                return [pad + f"WHILE {test}", *self.block(s.body, level + 1), pad + "ENDWHILE"]
            return [pad + f"while {test}", *self.block(s.body, level + 1), pad + "endwhile"]
        if isinstance(s, ir.RepeatUntil):
            test = self.expr(s.test)
            if self.d == "python":
                body = self.block(s.body, level + 1)
                return [
                    pad + "while True:",
                    *body,
                    pad + INDENT + f"if {test}:",
                    pad + INDENT * 2 + "break",
                ]
            if self.d == "aqa":
                return [pad + "REPEAT", *self.block(s.body, level + 1), pad + f"UNTIL {test}"]
            return [pad + "do", *self.block(s.body, level + 1), pad + f"until {test}"]
        if isinstance(s, ir.ForRange):
            return self.for_range(s, level)
        if isinstance(s, ir.ForEach):
            it = self.expr(s.iterable)
            if self.d == "python":
                return [pad + f"for {s.var} in {it}:", *self.block(s.body, level + 1)]
            if self.d == "aqa":
                return [
                    pad + f"FOR {s.var} IN {it}",
                    *self.block(s.body, level + 1),
                    pad + "ENDFOR",
                ]
            # ERL has no for-each: index through the array instead.
            self.report.notes.append(
                f"for-each over {it} written as an index loop (ERL has no for-each)"
            )
            idx = f"{s.var}_index"
            return [
                pad + f"for {idx} = 0 to {it}.length - 1",
                pad + INDENT + f"{s.var} = {it}[{idx}]",
                *self.block(s.body, level + 1),
                pad + f"next {idx}",
            ]
        if isinstance(s, ir.FuncDef):
            params = ", ".join(s.params)
            body = self.block(s.body, level + 1)
            if self.d == "python":
                return [pad + f"def {s.name}({params}):", *body, ""]
            if self.d == "aqa":
                return [pad + f"SUBROUTINE {s.name}({params})", *body, pad + "ENDSUBROUTINE", ""]
            kind = "function" if s.returns_value else "procedure"
            return [pad + f"{kind} {s.name}({params})", *body, pad + f"end{kind}", ""]
        if isinstance(s, ir.Return):
            value = "" if s.value is None else " " + self.expr(s.value)
            return [pad + ("RETURN" if self.d == "aqa" else "return") + value]
        return [pad + self.comment(f"unknown statement {type(s).__name__}")]

    def if_(self, s: ir.If, level: int) -> list[str]:
        pad = INDENT * level
        out: list[str] = []
        if self.d == "python":
            out.append(pad + f"if {self.expr(s.test)}:")
            out += self.block(s.body, level + 1)
            for test, body in s.elifs:
                out.append(pad + f"elif {self.expr(test)}:")
                out += self.block(body, level + 1)
            if s.orelse:
                out.append(pad + "else:")
                out += self.block(s.orelse, level + 1)
            return out
        kw = {"if": "IF", "then": "THEN", "elif": "ELSE IF", "else": "ELSE", "end": "ENDIF"}
        if self.d == "ocr":
            kw = {"if": "if", "then": "then", "elif": "elseif", "else": "else", "end": "endif"}
        out.append(pad + f"{kw['if']} {self.expr(s.test)} {kw['then']}")
        out += self.block(s.body, level + 1)
        for test, body in s.elifs:
            out.append(pad + f"{kw['elif']} {self.expr(test)} {kw['then']}")
            out += self.block(body, level + 1)
        if s.orelse:
            out.append(pad + kw["else"])
            out += self.block(s.orelse, level + 1)
        out.append(pad + kw["end"])
        return out

    def for_range(self, s: ir.ForRange, level: int) -> list[str]:
        pad = INDENT * level
        start, stop = self.expr(s.start), self.expr(s.stop)
        step = self.expr(s.step) if s.step is not None else None
        if self.d == "python":
            from staffroom.tools.pseudocode.from_python import plus_one

            upper = self.expr(plus_one(s.stop))
            if start == "0" and step is None:
                rng = f"range({upper})"
            elif step is None:
                rng = f"range({start}, {upper})"
            else:
                rng = f"range({start}, {upper}, {step})"
            return [pad + f"for {s.var} in {rng}:", *self.block(s.body, level + 1)]
        if self.d == "aqa":
            head = f"FOR {s.var} ← {start} TO {stop}" + (f" STEP {step}" if step else "")
            return [pad + head, *self.block(s.body, level + 1), pad + "ENDFOR"]
        head = f"for {s.var} = {start} to {stop}" + (f" step {step}" if step else "")
        return [pad + head, *self.block(s.body, level + 1), pad + f"next {s.var}"]

    # -- expressions ---------------------------------------------------------
    def expr(self, e: ir.Expr, parent_prec: int = 0) -> str:
        if isinstance(e, ir.Name):
            return e.id
        if isinstance(e, ir.Const):
            return self.const(e.value)
        if isinstance(e, ir.Raw):
            return e.text
        if isinstance(e, ir.BinOp):
            prec = _PREC[e.op]
            op = self.binop(e.op)
            left = self.expr(e.left, prec)
            right = self.expr(e.right, prec + 1 if e.op != "^" else prec)
            text = f"{left} {op} {right}"
            return f"({text})" if prec < parent_prec else text
        if isinstance(e, ir.Compare):
            prec = _PREC[e.op]
            text = f"{self.expr(e.left, prec + 1)} {self.cmp(e.op)} {self.expr(e.right, prec + 1)}"
            return f"({text})" if prec < parent_prec else text
        if isinstance(e, ir.BoolOp):
            prec = _PREC[e.op]
            op = e.op if self.d != "python" else e.op.lower()
            text = f"{self.expr(e.left, prec)} {op} {self.expr(e.right, prec + 1)}"
            return f"({text})" if prec < parent_prec else text
        if isinstance(e, ir.Not):
            op = "not" if self.d == "python" else "NOT"
            text = f"{op} {self.expr(e.operand, _PREC['NOT'])}"
            return f"({text})" if _PREC["NOT"] < parent_prec else text
        if isinstance(e, ir.Neg):
            return f"-{self.expr(e.operand, _PREC['NEG'])}"
        if isinstance(e, ir.Call):
            return self.call(e)
        if isinstance(e, ir.Method):
            return self.method(e)
        if isinstance(e, ir.Index):
            return f"{self.expr(e.obj, 9)}[{self.expr(e.index)}]"
        if isinstance(e, ir.Slice):
            return self.slice_(e)
        if isinstance(e, ir.ListLit):
            return "[" + ", ".join(self.expr(i) for i in e.items) + "]"
        return "?"

    def const(self, value: object) -> str:
        if isinstance(value, bool):
            if self.d == "ocr":
                return "true" if value else "false"
            return "True" if value else "False"
        if value is None:
            if self.d != "python":
                self.report.notes.append("None has no pseudocode equivalent; written as None")
            return "None"
        if isinstance(value, str):
            return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
        return repr(value)

    def binop(self, op: str) -> str:
        if self.d == "python":
            return {"DIV": "//", "MOD": "%", "^": "**"}.get(op, op)
        return op

    def cmp(self, op: str) -> str:
        if self.d == "aqa":
            return {"==": "=", "!=": "≠", "<=": "≤", ">=": "≥"}.get(op, op)
        return op

    def args(self, args: tuple[ir.Expr, ...]) -> str:
        return ", ".join(self.expr(a) for a in args)

    def call(self, e: ir.Call) -> str:
        a = e.args
        if e.func == "input":
            if self.d == "aqa":
                if a:
                    self.report.notes.append("input prompt written as a separate OUTPUT")
                return "USERINPUT"
            return f"input({self.args(a)})"
        if e.func == "len":
            if self.d == "ocr" and len(a) == 1:
                return f"{self.expr(a[0], 9)}.length"
            if self.d == "aqa":
                return f"LEN({self.args(a)})"
            return f"len({self.args(a)})"
        if e.func == "random":
            self.uses_random = True
            if self.d == "aqa":
                return f"RANDOM_INT({self.args(a)})"
            if self.d == "python":
                return f"random.randint({self.args(a)})"
            return f"random({self.args(a)})"
        if e.func in ("int", "float", "str", "bool") and self.d == "aqa" and len(a) == 1:
            inner = self.expr(a[0])
            name = {"int": "STRING_TO_INT", "float": "STRING_TO_REAL", "str": "INT_TO_STRING"}.get(
                e.func
            )
            if name:
                if e.func == "str":
                    self.report.notes.append(
                        "str() written as INT_TO_STRING (use REAL_TO_STRING for reals)"
                    )
                return f"{name}({inner})"
        if e.func == "float" and self.d == "ocr":
            return f"real({self.args(a)})"
        if e.func == "ord":
            return {"ocr": "ASC", "aqa": "CHAR_TO_CODE", "python": "ord"}[
                self.d
            ] + f"({self.args(a)})"
        if e.func == "chr":
            return {"ocr": "CHR", "aqa": "CODE_TO_CHAR", "python": "chr"}[
                self.d
            ] + f"({self.args(a)})"
        return f"{e.func}({self.args(a)})"

    def method(self, e: ir.Method) -> str:
        obj = self.expr(e.obj, 9)
        if e.name in ("upper", "lower"):
            if self.d == "ocr":
                return f"{obj}.{e.name}"
            if self.d == "aqa":
                self.report.notes.append(f".{e.name}() has no AQA equivalent; kept as written")
            return f"{obj}.{e.name}()"
        if e.name in ("readline", "readLine"):
            return f"{obj}.{'readline' if self.d == 'python' else 'readLine'}()"
        if e.name in ("write", "writeLine"):
            return f"{obj}.{'write' if self.d == 'python' else 'writeLine'}({self.args(e.args)})"
        if e.name == "append":
            if self.d != "python":
                self.report.notes.append(
                    f"{obj}.append: pseudocode arrays are fixed size; kept as written"
                )
            return f"{obj}.append({self.args(e.args)})"
        if e.name == "substring" and self.d != "ocr":
            start, length = e.args
            if self.d == "python":
                return self.slice_(ir.Slice(e.obj, start, ir.BinOp("+", start, length)))
            end = self.expr(fold(ir.BinOp("-", ir.BinOp("+", start, length), ir.Const(1))))
            return f"SUBSTRING({self.expr(start)}, {end}, {obj})"
        return f"{obj}.{e.name}({self.args(e.args)})"

    def slice_(self, e: ir.Slice) -> str:
        obj = self.expr(e.obj, 9)
        lower, upper = fold(e.lower), fold(e.upper)
        if self.d == "python":
            lo = "" if lower == ir.Const(0) else self.expr(lower)
            return f"{obj}[{lo}:{self.expr(upper)}]"
        if self.d == "aqa":
            last = self.expr(fold(ir.BinOp("-", upper, ir.Const(1))))
            return f"SUBSTRING({self.expr(lower)}, {last}, {obj})"
        length = fold(ir.BinOp("-", upper, lower))
        return f"{obj}.substring({self.expr(lower)}, {self.expr(length)})"


def _int(e: ir.Expr) -> int | None:
    if isinstance(e, ir.Const) and isinstance(e.value, int) and not isinstance(e.value, bool):
        return e.value
    return None


def fold(e: ir.Expr) -> ir.Expr:
    """Constant-fold integer + and - so ``1 + 2 - 1`` reads as ``2`` and
    ``(x + 1) - 1`` reads as ``x``."""
    if not (isinstance(e, ir.BinOp) and e.op in ("+", "-")):
        return e
    left, right = fold(e.left), fold(e.right)
    lv, rv = _int(left), _int(right)
    if lv is not None and rv is not None:
        return ir.Const(lv + rv if e.op == "+" else lv - rv)
    if rv == 0:
        return left
    if isinstance(left, ir.BinOp) and left.op in ("+", "-") and rv is not None:
        inner = _int(left.right)
        if inner is not None:
            total = (inner if left.op == "+" else -inner) + (rv if e.op == "+" else -rv)
            if total == 0:
                return left.left
            return ir.BinOp("+" if total > 0 else "-", left.left, ir.Const(abs(total)))
    return ir.BinOp(e.op, left, right)


def emit(prog: ir.Program, dialect: Dialect) -> tuple[str, EmitReport]:
    emitter = Emitter(dialect)
    text = emitter.program(prog)
    return text, emitter.report
