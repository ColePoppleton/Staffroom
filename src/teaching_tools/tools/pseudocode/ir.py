"""The intermediate representation: the GCSE subset, as plain data.

Both directions pass through here, so what cannot be expressed in the IR
cannot be translated, and says so (``Untranslatable``)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field


# ---------------------------------------------------------------- expressions
@dataclass(frozen=True)
class Name:
    id: str


@dataclass(frozen=True)
class Const:
    value: int | float | str | bool | None


@dataclass(frozen=True)
class BinOp:
    op: str  # + - * / DIV MOD ^
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Compare:
    op: str  # == != < <= > >=
    left: Expr
    right: Expr


@dataclass(frozen=True)
class BoolOp:
    op: str  # AND OR
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Not:
    operand: Expr


@dataclass(frozen=True)
class Neg:
    operand: Expr


@dataclass(frozen=True)
class Call:
    """A call to a builtin or user function. Builtins used by name:
    input, int, float, str, bool, len, random, open, asc, chr, user functions."""

    func: str
    args: tuple[Expr, ...]


@dataclass(frozen=True)
class Method:
    """``obj.name(args)``: upper, lower, substring(start, length), readLine,
    writeLine, close, endOfFile, append."""

    obj: Expr
    name: str
    args: tuple[Expr, ...] = ()


@dataclass(frozen=True)
class Index:
    obj: Expr
    index: Expr


@dataclass(frozen=True)
class Slice:
    obj: Expr
    lower: Expr
    upper: Expr  # exclusive, Python style


@dataclass(frozen=True)
class ListLit:
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class Raw:
    """Expression text we could not understand, kept verbatim."""

    text: str


Expr = (
    Name
    | Const
    | BinOp
    | Compare
    | BoolOp
    | Not
    | Neg
    | Call
    | Method
    | Index
    | Slice
    | ListLit
    | Raw
)


# ---------------------------------------------------------------- statements
@dataclass
class Assign:
    target: Expr  # Name or Index
    value: Expr


@dataclass
class Output:
    args: tuple[Expr, ...]


@dataclass
class ExprStmt:
    expr: Expr


@dataclass
class If:
    test: Expr
    body: list[Stmt]
    elifs: list[tuple[Expr, list[Stmt]]] = field(default_factory=list)
    orelse: list[Stmt] = field(default_factory=list)


@dataclass
class While:
    test: Expr
    body: list[Stmt]


@dataclass
class RepeatUntil:
    body: list[Stmt]
    test: Expr


@dataclass
class ForRange:
    var: str
    start: Expr
    stop: Expr  # inclusive, pseudocode style
    step: Expr | None
    body: list[Stmt]


@dataclass
class ForEach:
    var: str
    iterable: Expr
    body: list[Stmt]


@dataclass
class FuncDef:
    name: str
    params: tuple[str, ...]
    body: list[Stmt]
    returns_value: bool


@dataclass
class Return:
    value: Expr | None


@dataclass
class ArrayDecl:
    name: str
    size: Expr


@dataclass
class Comment:
    text: str


@dataclass
class Untranslatable:
    source: str
    reason: str


@dataclass
class Pass:
    pass


Stmt = (
    Assign
    | Output
    | ExprStmt
    | If
    | While
    | RepeatUntil
    | ForRange
    | ForEach
    | FuncDef
    | Return
    | ArrayDecl
    | Comment
    | Untranslatable
    | Pass
)


@dataclass
class Program:
    body: list[Stmt] = field(default_factory=list)


def walk(stmts: list[Stmt]) -> Iterator[Stmt]:
    for s in stmts:
        yield s
        for child in _children(s):
            yield from walk(child)


def _children(s: Stmt) -> list[list[Stmt]]:
    if isinstance(s, If):
        return [s.body, *(b for _, b in s.elifs), s.orelse]
    if isinstance(s, While | RepeatUntil | ForRange | ForEach | FuncDef):
        return [s.body]
    return []
