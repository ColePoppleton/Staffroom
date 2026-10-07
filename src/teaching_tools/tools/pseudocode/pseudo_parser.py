"""Pseudocode (OCR ERL or AQA) → IR.

One tokenizer, one recursive-descent parser, two keyword tables. Lines that
cannot be parsed become ``Untranslatable`` and are listed in the report."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from teaching_tools.tools.pseudocode import ir

PseudoDialect = Literal["ocr", "aqa"]

_TOKEN = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
  | (?P<num>\d+\.\d+|\d+)
  | (?P<op><-|←|==|!=|≠|<=|≤|>=|≥|[-+*/^<>=()\[\],.:])
  | (?P<name>[A-Za-z_][A-Za-z_0-9]*)
""",
    re.VERBOSE,
)

_WORD_OPS = {"and": "AND", "or": "OR", "not": "NOT", "mod": "MOD", "div": "DIV"}
_CMP_NORMAL = {
    "=": "==",
    "≠": "!=",
    "≤": "<=",
    "≥": ">=",
    "==": "==",
    "!=": "!=",
    "<": "<",
    "<=": "<=",
    ">": ">",
    ">=": ">=",
}


@dataclass
class Tok:
    kind: str  # str num op name eof
    text: str


@dataclass
class ParseReport:
    dropped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class ParseError(Exception):
    pass


def tokenize(line: str) -> list[Tok]:
    out: list[Tok] = []
    pos = 0
    while pos < len(line):
        m = _TOKEN.match(line, pos)
        if m is None:
            raise ParseError(f"unexpected character {line[pos]!r}")
        pos = m.end()
        kind = m.lastgroup or ""
        if kind == "ws":
            continue
        text = m.group()
        if kind == "name" and text.lower() in _WORD_OPS:
            out.append(Tok("op", _WORD_OPS[text.lower()]))
        else:
            out.append(Tok(kind, text))
    out.append(Tok("eof", ""))
    return out


class ExprParser:
    def __init__(self, tokens: list[Tok], dialect: PseudoDialect) -> None:
        self.toks = tokens
        self.i = 0
        self.d = dialect

    def peek(self) -> Tok:
        return self.toks[self.i]

    def take(self) -> Tok:
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def accept(self, text: str, kind: str = "op") -> bool:
        tok = self.peek()
        if tok.kind == kind and tok.text == text:
            self.i += 1
            return True
        return False

    def expect(self, text: str, kind: str = "op") -> None:
        if not self.accept(text, kind):
            raise ParseError(f"expected {text!r}, found {self.peek().text!r}")

    def at_end(self) -> bool:
        return self.peek().kind == "eof"

    # precedence climbing ----------------------------------------------------
    def expr(self) -> ir.Expr:
        return self.or_()

    def or_(self) -> ir.Expr:
        left = self.and_()
        while self.accept("OR"):
            left = ir.BoolOp("OR", left, self.and_())
        return left

    def and_(self) -> ir.Expr:
        left = self.not_()
        while self.accept("AND"):
            left = ir.BoolOp("AND", left, self.not_())
        return left

    def not_(self) -> ir.Expr:
        if self.accept("NOT"):
            return ir.Not(self.not_())
        return self.comparison()

    def comparison(self) -> ir.Expr:
        left = self.additive()
        tok = self.peek()
        if (tok.kind == "op" and tok.text in _CMP_NORMAL and tok.text != "=") or (
            tok.kind == "op" and tok.text == "=" and self.d == "aqa"
        ):
            self.take()
            return ir.Compare(_CMP_NORMAL[tok.text], left, self.additive())
        return left

    def additive(self) -> ir.Expr:
        left = self.term()
        while self.peek().kind == "op" and self.peek().text in ("+", "-"):
            op = self.take().text
            left = ir.BinOp(op, left, self.term())
        return left

    def term(self) -> ir.Expr:
        left = self.unary()
        while self.peek().kind == "op" and self.peek().text in ("*", "/", "DIV", "MOD"):
            op = self.take().text
            left = ir.BinOp(op, left, self.unary())
        return left

    def unary(self) -> ir.Expr:
        if self.accept("-"):
            inner = self.unary()
            if isinstance(inner, ir.Const) and isinstance(inner.value, int | float):
                return ir.Const(-inner.value)
            return ir.Neg(inner)
        return self.power()

    def power(self) -> ir.Expr:
        base = self.postfix()
        if self.accept("^"):
            return ir.BinOp("^", base, self.unary())
        return base

    def postfix(self) -> ir.Expr:
        node = self.primary()
        while True:
            if self.accept("["):
                index = self.expr()
                self.expect("]")
                node = ir.Index(node, index)
            elif self.accept("."):
                name = self.take().text
                if self.accept("("):
                    args = self.arglist()
                    node = ir.Method(node, name, args)
                elif name == "length":
                    node = ir.Call("len", (node,))
                else:
                    node = ir.Method(node, name, ())
            else:
                return node

    def arglist(self) -> tuple[ir.Expr, ...]:
        args: list[ir.Expr] = []
        if self.accept(")"):
            return ()
        while True:
            args.append(self.expr())
            if self.accept(")"):
                return tuple(args)
            self.expect(",")

    def primary(self) -> ir.Expr:
        tok = self.take()
        if tok.kind == "num":
            return ir.Const(float(tok.text) if "." in tok.text else int(tok.text))
        if tok.kind == "str":
            return ir.Const(_unquote(tok.text))
        if tok.kind == "op" and tok.text == "(":
            inner = self.expr()
            self.expect(")")
            return inner
        if tok.kind == "op" and tok.text == "[":
            items: list[ir.Expr] = []
            if not self.accept("]"):
                while True:
                    items.append(self.expr())
                    if self.accept("]"):
                        break
                    self.expect(",")
            return ir.ListLit(tuple(items))
        if tok.kind == "name":
            return self.name_or_call(tok.text)
        raise ParseError(f"unexpected {tok.text!r}")

    def name_or_call(self, name: str) -> ir.Expr:
        lower = name.lower()
        if lower in ("true", "false"):
            return ir.Const(lower == "true")
        if name == "USERINPUT":
            return ir.Call("input", ())
        if self.accept("("):
            args = self.arglist()
            return self.builtin(name, args)
        return ir.Name(name)

    def builtin(self, name: str, args: tuple[ir.Expr, ...]) -> ir.Expr:
        upper = name.upper()
        if upper == "LEN":
            return ir.Call("len", args)
        if upper == "SUBSTRING" and len(args) == 3:  # AQA: SUBSTRING(start, end, s) inclusive end
            start, end, s = args
            return ir.Slice(s, start, ir.BinOp("+", end, ir.Const(1)))
        if upper in ("STRING_TO_INT",):
            return ir.Call("int", args)
        if upper in ("STRING_TO_REAL",):
            return ir.Call("float", args)
        if upper in ("INT_TO_STRING", "REAL_TO_STRING"):
            return ir.Call("str", args)
        if upper in ("RANDOM_INT", "RANDOM"):
            return ir.Call("random", args)
        if upper in ("CHAR_TO_CODE", "ASC"):
            return ir.Call("ord", args)
        if upper in ("CODE_TO_CHAR", "CHR"):
            return ir.Call("chr", args)
        if name == "real":
            return ir.Call("float", args)
        return ir.Call(name, args)


def _unquote(text: str) -> str:
    body = text[1:-1]
    return body.encode("utf-8").decode("unicode_escape") if "\\" in body else body


def parse_expr(text: str, dialect: PseudoDialect) -> ir.Expr:
    parser = ExprParser(tokenize(text), dialect)
    node = parser.expr()
    if not parser.at_end():
        raise ParseError(f"unexpected {parser.peek().text!r} after expression")
    return node


# ---------------------------------------------------------------- statements
@dataclass
class Line:
    number: int
    text: str  # stripped
    indent: int


class StmtParser:
    def __init__(self, source: str, dialect: PseudoDialect) -> None:
        self.d = dialect
        self.report = ParseReport()
        self.lines = [
            Line(i, ln.strip(), len(ln) - len(ln.lstrip()))
            for i, ln in enumerate(source.splitlines(), 1)
        ]
        self.pos = 0

    def program(self) -> ir.Program:
        body = self.block(end_words=())
        return ir.Program(body)

    # -- helpers -------------------------------------------------------------
    def peek(self) -> Line | None:
        return self.lines[self.pos] if self.pos < len(self.lines) else None

    def words(self, line: Line) -> list[str]:
        return line.text.replace("(", " (").split()

    def first(self, line: Line) -> str:
        w = self.words(line)
        return w[0].lower() if w else ""

    def rest_after(self, line: Line, n_words: int) -> str:
        parts = line.text.split(None, n_words)
        return parts[n_words] if len(parts) > n_words else ""

    def drop(self, line: Line, reason: str) -> ir.Untranslatable:
        self.report.dropped.append(f"line {line.number}: {reason}: {line.text}")
        return ir.Untranslatable(line.text, reason)

    def block(self, end_words: tuple[str, ...]) -> list[ir.Stmt]:
        """Statements until a line starting with one of ``end_words`` (left
        for the caller to consume)."""
        out: list[ir.Stmt] = []
        while (line := self.peek()) is not None:
            if not line.text:
                self.pos += 1
                continue
            if self.first(line) in end_words or self.first(line).rstrip(":") in end_words:
                return out
            out.append(self.statement())
        return out

    def expect_end(self, *words: str) -> None:
        line = self.peek()
        if line is None or self.first(line) not in words:
            raise ParseError(f"expected {' or '.join(words)}")
        self.pos += 1

    def expr(self, text: str, line: Line) -> ir.Expr:
        try:
            return parse_expr(text, self.d)
        except ParseError as exc:
            self.report.notes.append(f"line {line.number}: kept as written: {text} ({exc})")
            return ir.Raw(text)

    # -- the statement switch ------------------------------------------------
    def statement(self) -> ir.Stmt:
        line = self.peek()
        assert line is not None
        self.pos += 1
        text = line.text
        head = self.first(line)
        try:
            if text.startswith("//") or text.startswith("#"):
                return ir.Comment(text.lstrip("/# ").strip())
            if head in ("print", "output"):
                arg_text = (
                    self.rest_after(line, 1) if head == "output" else text[len("print") :].strip()
                )
                if head == "print" and arg_text.startswith("(") and arg_text.endswith(")"):
                    arg_text = arg_text[1:-1]
                return ir.Output(self.exprs(arg_text, line))
            if head == "if":
                return self.if_(line)
            if head == "while":
                test = self.expr(self.rest_after(line, 1), line)
                body = self.block(("endwhile",))
                self.expect_end("endwhile")
                return ir.While(test, body)
            if head in ("do", "repeat"):
                body = self.block(("until",))
                until = self.peek()
                assert until is not None
                self.pos += 1
                return ir.RepeatUntil(body, self.expr(self.rest_after(until, 1), until))
            if head == "for":
                return self.for_(line)
            if head in ("function", "procedure", "subroutine"):
                return self.func(line, head)
            if head == "return":
                rest = self.rest_after(line, 1)
                return ir.Return(self.expr(rest, line) if rest else None)
            if head == "array" and self.d == "ocr":
                m = re.match(r"array\s+(\w+)\s*\[(.+)\]\s*$", text)
                if m:
                    return ir.ArrayDecl(m.group(1), self.expr(m.group(2), line))
            if head in ("switch", "case"):
                return self.drop(line, "switch/case is not supported")
            # assignment?
            m = re.match(r"^([A-Za-z_]\w*(?:\[[^\]]+\])?)\s*(←|<-|=)(?!=)\s*(.+)$", text)
            if m and not (self.d == "aqa" and m.group(2) == "=" and False):
                target = self.expr(m.group(1), line)
                return ir.Assign(target, self.expr(m.group(3), line))
            # bare call
            node = self.expr(text, line)
            if isinstance(node, ir.Raw):
                return self.drop(line, "could not parse")
            return ir.ExprStmt(node)
        except ParseError as exc:
            return self.drop(line, str(exc))

    def exprs(self, text: str, line: Line) -> tuple[ir.Expr, ...]:
        # Split top-level commas.
        parts: list[str] = []
        depth = 0
        quote: str | None = None
        current = ""
        for ch in text:
            if quote:
                current += ch
                if ch == quote:
                    quote = None
                continue
            if ch in "\"'":
                quote = ch
            elif ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append(current)
                current = ""
                continue
            current += ch
        if current.strip():
            parts.append(current)
        return tuple(self.expr(p.strip(), line) for p in parts)

    def if_(self, line: Line) -> ir.Stmt:
        test = self.expr(_strip_then(self.rest_after(line, 1)), line)
        body = self.block(("elseif", "else", "endif"))
        elifs: list[tuple[ir.Expr, list[ir.Stmt]]] = []
        orelse: list[ir.Stmt] = []
        while (nxt := self.peek()) is not None:
            head = self.first(nxt)
            words = self.words(nxt)
            if head == "elseif" or (head == "else" and len(words) > 1 and words[1].lower() == "if"):
                self.pos += 1
                n = 1 if head == "elseif" else 2
                elifs.append(
                    (
                        self.expr(_strip_then(self.rest_after(nxt, n)), nxt),
                        self.block(("elseif", "else", "endif")),
                    )
                )
            elif head == "else":
                self.pos += 1
                orelse = self.block(("endif",))
            else:
                break
        self.expect_end("endif")
        return ir.If(test, body, elifs, orelse)

    def for_(self, line: Line) -> ir.Stmt:
        m = re.match(
            r"for\s+(\w+)\s*(?:=|←|<-)\s*(.+?)\s+to\s+(.+?)(?:\s+step\s+(.+))?\s*$", line.text, re.I
        )
        if m:
            var, start, stop, step = m.groups()
            body = self.block(("next", "endfor"))
            self.expect_end("next", "endfor")
            return ir.ForRange(
                var,
                self.expr(start, line),
                self.expr(stop, line),
                self.expr(step, line) if step else None,
                body,
            )
        m = re.match(r"for\s+(?:each\s+)?(\w+)\s+in\s+(.+)$", line.text, re.I)
        if m:
            body = self.block(("next", "endfor"))
            self.expect_end("next", "endfor")
            return ir.ForEach(m.group(1), self.expr(m.group(2), line), body)
        raise ParseError("could not read the for loop header")

    def func(self, line: Line, head: str) -> ir.Stmt:
        m = re.match(r"\w+\s+(\w+)\s*\((.*)\)\s*$", line.text)
        if not m:
            raise ParseError("could not read the subroutine header")
        name, params = m.group(1), tuple(p.strip() for p in m.group(2).split(",") if p.strip())
        ends = {
            "function": ("endfunction",),
            "procedure": ("endprocedure",),
            "subroutine": ("endsubroutine",),
        }[head]
        body = self.block(ends)
        self.expect_end(*ends)
        returns = any(isinstance(s, ir.Return) and s.value is not None for s in ir.walk(body))
        return ir.FuncDef(name, params, body, returns)


def _strip_then(text: str) -> str:
    text = text.strip()
    if text.lower().endswith(" then"):
        return text[:-5].strip()
    return text.rstrip(":").strip()


def parse_pseudo(source: str, dialect: PseudoDialect) -> tuple[ir.Program, ParseReport]:
    parser = StmtParser(source, dialect)
    program = parser.program()
    return program, parser.report
