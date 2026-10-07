"""Python source → IR. Outside the subset, a statement becomes
``Untranslatable`` (kept as a comment in the output and listed in the
report); an expression we cannot read becomes ``Raw`` text."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from teaching_tools.tools.pseudocode import ir

_BIN = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "DIV",
    ast.Mod: "MOD",
    ast.Pow: "^",
}
_CMP = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}
_CASTS = {"int", "float", "str", "bool", "len", "input", "open", "ord", "chr", "round", "abs"}


@dataclass
class Report:
    dropped: list[str] = field(default_factory=list)  # "line N: reason"
    notes: list[str] = field(default_factory=list)


class Converter:
    def __init__(self, source: str) -> None:
        self.source = source
        self.lines = source.splitlines()
        self.report = Report()

    # -- entry -------------------------------------------------------------
    def program(self) -> ir.Program:
        tree = ast.parse(self.source)
        return ir.Program(self.block(tree.body, top=True))

    def block(
        self, stmts: list[ast.stmt], *, top: bool = False, after: int | None = None
    ) -> list[ir.Stmt]:
        """``after`` is the header line of the enclosing statement, so comments
        above it are not re-emitted inside the block."""
        out: list[ir.Stmt] = []
        if top:
            last_line = 0
        elif after is not None:
            last_line = after
        else:
            last_line = stmts[0].lineno - 1 if stmts else 0
        for node in stmts:
            out += self.comments_between(last_line, node.lineno)
            out.append(self.stmt(node))
            last_line = node.end_lineno or node.lineno
        if top:
            out += self.comments_between(last_line, len(self.lines) + 1)
        return out

    def comments_between(self, after: int, before: int) -> list[ir.Stmt]:
        found: list[ir.Stmt] = []
        for n in range(after + 1, before):
            text = self.lines[n - 1].strip() if n - 1 < len(self.lines) else ""
            if text.startswith("#"):
                found.append(ir.Comment(text[1:].strip()))
        return found

    def segment(self, node: ast.AST) -> str:
        return (ast.get_source_segment(self.source, node) or "").strip()

    def drop(self, node: ast.stmt, reason: str) -> ir.Untranslatable:
        text = self.segment(node).splitlines()[0] if self.segment(node) else ""
        self.report.dropped.append(f"line {node.lineno}: {reason}: {text}")
        return ir.Untranslatable(text, reason)

    # -- statements ----------------------------------------------------------
    def stmt(self, node: ast.stmt) -> ir.Stmt:
        if isinstance(node, ast.Expr):
            call = node.value
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "print"
            ):
                if call.keywords:
                    self.report.notes.append(f"line {node.lineno}: print options (sep/end) ignored")
                return ir.Output(tuple(self.expr(a) for a in call.args))
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return ir.Comment(node.value.value.strip())
            return ir.ExprStmt(self.expr(node.value))
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                return self.drop(node, "multiple assignment targets")
            target = node.targets[0]
            value = node.value
            if (
                isinstance(target, ast.Name)
                and isinstance(value, ast.BinOp)
                and isinstance(value.op, ast.Mult)
                and isinstance(value.left, ast.List)
                and len(value.left.elts) == 1
            ):
                return ir.ArrayDecl(target.id, self.expr(value.right))
            if isinstance(target, ast.Name | ast.Subscript):
                return ir.Assign(self.expr(target), self.expr(value))
            return self.drop(node, "unsupported assignment target")
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name | ast.Subscript):
            op = _BIN.get(type(node.op))
            if op is None:
                return self.drop(node, "unsupported operator")
            lhs = self.expr(node.target)
            return ir.Assign(lhs, ir.BinOp(op, lhs, self.expr(node.value)))
        if isinstance(node, ast.If):
            elifs: list[tuple[ir.Expr, list[ir.Stmt]]] = []
            orelse = node.orelse
            while len(orelse) == 1 and isinstance(orelse[0], ast.If):
                sub = orelse[0]
                elifs.append((self.expr(sub.test), self.block(sub.body, after=sub.lineno)))
                orelse = sub.orelse
            return ir.If(
                self.expr(node.test),
                self.block(node.body, after=node.lineno),
                elifs,
                self.block(orelse),
            )
        if isinstance(node, ast.While):
            if node.orelse:
                return self.drop(node, "while/else")
            return ir.While(self.expr(node.test), self.block(node.body, after=node.lineno))
        if isinstance(node, ast.For):
            if node.orelse or not isinstance(node.target, ast.Name):
                return self.drop(node, "unsupported for loop")
            it = node.iter
            if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "range":
                args = [self.expr(a) for a in it.args]
                start: ir.Expr
                stop: ir.Expr
                step: ir.Expr | None
                if len(args) == 1:
                    start, stop, step = ir.Const(0), args[0], None
                elif len(args) == 2:
                    start, stop, step = args[0], args[1], None
                elif len(args) == 3:
                    start, stop, step = args[0], args[1], args[2]
                else:
                    return self.drop(node, "range() needs 1 to 3 arguments")
                return ir.ForRange(
                    node.target.id, start, minus_one(stop), step, self.block(node.body)
                )
            return ir.ForEach(
                node.target.id, self.expr(it), self.block(node.body, after=node.lineno)
            )
        if isinstance(node, ast.FunctionDef):
            if node.args.vararg or node.args.kwarg or node.args.kwonlyargs or node.args.defaults:
                return self.drop(node, "only simple parameters are supported")
            body = self.block(node.body, after=node.lineno)
            returns = any(isinstance(s, ir.Return) and s.value is not None for s in ir.walk(body))
            return ir.FuncDef(node.name, tuple(a.arg for a in node.args.args), body, returns)
        if isinstance(node, ast.Return):
            return ir.Return(self.expr(node.value) if node.value is not None else None)
        if isinstance(node, ast.Pass):
            return ir.Pass()
        if isinstance(node, ast.Import | ast.ImportFrom):
            names = [a.name for a in node.names]
            if names == ["random"]:
                self.report.notes.append(
                    f"line {node.lineno}: 'import random' is implied in pseudocode"
                )
                return ir.Comment("uses random")
            return self.drop(node, "imports are not part of the subset")
        if isinstance(node, ast.Break):
            return self.drop(node, "break has no pseudocode equivalent")
        if isinstance(node, ast.Continue):
            return self.drop(node, "continue has no pseudocode equivalent")
        return self.drop(node, f"{type(node).__name__.lower()} is not in the GCSE subset")

    # -- expressions ---------------------------------------------------------
    def expr(self, node: ast.expr) -> ir.Expr:
        if isinstance(node, ast.Name):
            return ir.Name(node.id)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool | int | float | str) or node.value is None:
                return ir.Const(node.value)
            return self.raw(node)
        if isinstance(node, ast.BinOp):
            op = _BIN.get(type(node.op))
            if op is None:
                return self.raw(node)
            return ir.BinOp(op, self.expr(node.left), self.expr(node.right))
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = _CMP.get(type(node.ops[0]))
            if op is None:
                return self.raw(node)
            return ir.Compare(op, self.expr(node.left), self.expr(node.comparators[0]))
        if isinstance(node, ast.BoolOp):
            op = "AND" if isinstance(node.op, ast.And) else "OR"
            result = self.expr(node.values[0])
            for value in node.values[1:]:
                result = ir.BoolOp(op, result, self.expr(value))
            return result
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return ir.Not(self.expr(node.operand))
            if isinstance(node.op, ast.USub):
                inner = self.expr(node.operand)
                if isinstance(inner, ir.Const) and isinstance(inner.value, int | float):
                    return ir.Const(-inner.value)
                return ir.Neg(inner)
            return self.raw(node)
        if isinstance(node, ast.Call):
            if node.keywords:
                return self.raw(node)
            args = tuple(self.expr(a) for a in node.args)
            if isinstance(node.func, ast.Name):
                return ir.Call(node.func.id, args)
            if isinstance(node.func, ast.Attribute):
                owner = node.func.value
                if isinstance(owner, ast.Name) and owner.id == "random":
                    if node.func.attr == "randint":
                        return ir.Call("random", args)
                    return self.raw(node)
                return ir.Method(self.expr(owner), node.func.attr, args)
            return self.raw(node)
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                lower = self.expr(node.slice.lower) if node.slice.lower else ir.Const(0)
                if node.slice.upper is None or node.slice.step is not None:
                    return self.raw(node)
                return ir.Slice(self.expr(node.value), lower, self.expr(node.slice.upper))
            return ir.Index(self.expr(node.value), self.expr(node.slice))
        if isinstance(node, ast.List | ast.Tuple):
            return ir.ListLit(tuple(self.expr(e) for e in node.elts))
        return self.raw(node)

    def raw(self, node: ast.expr) -> ir.Raw:
        text = self.segment(node)
        self.report.notes.append(f"line {node.lineno}: kept as written (not in the subset): {text}")
        return ir.Raw(text)


def minus_one(expr: ir.Expr) -> ir.Expr:
    if (
        isinstance(expr, ir.Const)
        and isinstance(expr.value, int)
        and not isinstance(expr.value, bool)
    ):
        return ir.Const(expr.value - 1)
    if isinstance(expr, ir.BinOp) and expr.op == "+" and expr.right == ir.Const(1):
        return expr.left
    return ir.BinOp("-", expr, ir.Const(1))


def plus_one(expr: ir.Expr) -> ir.Expr:
    if (
        isinstance(expr, ir.Const)
        and isinstance(expr.value, int)
        and not isinstance(expr.value, bool)
    ):
        return ir.Const(expr.value + 1)
    if isinstance(expr, ir.BinOp) and expr.op == "-" and expr.right == ir.Const(1):
        return expr.left
    return ir.BinOp("+", expr, ir.Const(1))


def from_python(source: str) -> tuple[ir.Program, Report]:
    converter = Converter(source)
    program = converter.program()
    return program, converter.report
