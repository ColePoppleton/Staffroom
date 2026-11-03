"""Which wrong variable a pupil would plausibly type (#48). Pure: an ``ast``
tree in, names out; no I/O.

Bugs (its ``wrong_variable`` bug) and Parsons (its wrong-variable
distractors) both ask the same question, so they share this one rule. A
pupil who types the wrong name usually types one they have just been using,
of the same sort: ``total`` for ``count``, not the list ``scores`` for a
number. So the stand-in is a name that

* is set in the same scope (the same function, or the top level) on an
  earlier line, so it already exists when the line runs (no NameError);
* looks like the same kind of value as far as the program's own assignments
  show (no TypeError);
* of those, was set most recently; ties go to the name set first.

Kinds are a coarse guess: ``number``, ``str``, ``list``, ``dict``, ``bool``
or ``unknown`` (a parameter, a value from an unknown call, anything
unclear). A name of unknown kind has no stand-in unless the caller asks for
a guess (:meth:`Scopes.stand_in`).

Names bound inside a lambda or a comprehension live only there: never a
stand-in for the program's names. Which *uses* of a name each tool is willing
to swap (Parsons leaves names in literals alone, for example) is the tool's
business, not this module's."""

from __future__ import annotations

import ast
from typing import Literal

NameKind = Literal["number", "str", "list", "dict", "bool", "unknown"]

_NUMBER_CALLS = {"int", "float", "len", "sum", "round", "abs", "min", "max", "ord"}
_STR_CALLS = {"str", "input", "chr", "repr", "format"}
_LIST_CALLS = {"list", "sorted"}
SCOPES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)
# Names bound in these live only inside them.
OWN_NAMES = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


class Scopes:
    """Which names each scope sets, on which lines, and of what kind."""

    def __init__(self, tree: ast.Module) -> None:
        self.tree = tree
        self.stores: dict[ast.AST, dict[str, list[int]]] = {}  # scope -> name -> lines
        self.values: dict[str, list[ast.expr]] = {}  # name -> what it was set to
        self.items: dict[str, list[ast.expr]] = {}  # loop variable -> what it loops over
        self.scope_of: dict[ast.Name, ast.AST] = {}  # every Name -> its scope
        self._walk(tree, tree)
        # Names set from other names settle in a few passes. Each pass reads
        # only the previous one, so the result does not depend on set order.
        self.kinds: dict[str, NameKind] = {}
        for _ in range(10):
            settled = {name: self._name_kind(name) for name in self.values.keys() | self.items}
            if settled == self.kinds:
                break
            self.kinds = settled

    def _walk(self, node: ast.AST, scope: ast.AST, record: bool = True) -> None:
        for child in ast.iter_child_nodes(node):
            inner = child if isinstance(child, SCOPES) else scope
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                args = child.args
                for a in args.posonlyargs + args.args + args.kwonlyargs:
                    self.stores.setdefault(child, {}).setdefault(a.arg, []).append(child.lineno)
            if isinstance(child, ast.Name):
                self.scope_of[child] = scope
                if record and isinstance(child.ctx, ast.Store):
                    self.stores.setdefault(scope, {}).setdefault(child.id, []).append(child.lineno)
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        self.values.setdefault(target.id, []).append(child.value)
            elif isinstance(child, ast.AnnAssign | ast.AugAssign):
                if isinstance(child.target, ast.Name) and child.value is not None:
                    self.values.setdefault(child.target.id, []).append(child.value)
            elif isinstance(child, ast.For) and isinstance(child.target, ast.Name):
                self.items.setdefault(child.target.id, []).append(child.iter)
            self._walk(child, inner, record and not isinstance(child, OWN_NAMES))

    def _name_kind(self, name: str) -> NameKind:
        found = {self._kind(v) for v in self.values.get(name, [])}
        found |= {self._item_kind(it) for it in self.items.get(name, [])}
        return found.pop() if len(found) == 1 else "unknown"

    def _kind(self, value: ast.expr) -> NameKind:
        if isinstance(value, ast.Constant):
            v = value.value
            if isinstance(v, bool):
                return "bool"
            if isinstance(v, int | float):
                return "number"
            return "str" if isinstance(v, str) else "unknown"
        if isinstance(value, ast.JoinedStr):
            return "str"
        if isinstance(value, ast.List | ast.ListComp):
            return "list"
        if isinstance(value, ast.Dict | ast.DictComp):
            return "dict"
        if isinstance(value, ast.Compare | ast.BoolOp):
            return "bool"
        if isinstance(value, ast.Name):
            return self.kinds.get(value.id, "unknown")
        if isinstance(value, ast.UnaryOp):
            return "bool" if isinstance(value.op, ast.Not) else self._kind(value.operand)
        if isinstance(value, ast.BinOp):
            left, right = self._kind(value.left), self._kind(value.right)
            if isinstance(value.op, ast.Div) and "number" in (left, right):
                return "number"
            return left if left != "unknown" else right
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            fn = value.func.id
            if fn in _NUMBER_CALLS:
                return "number"
            if fn in _STR_CALLS:
                return "str"
            if fn in _LIST_CALLS:
                return "list"
            if fn == "bool":
                return "bool"
            if fn == "dict":
                return "dict"
        return "unknown"

    def _item_kind(self, iterable: ast.expr) -> NameKind:
        """The kind of value a ``for`` loop over ``iterable`` hands out."""
        if (
            isinstance(iterable, ast.Call)
            and isinstance(iterable.func, ast.Name)
            and iterable.func.id == "range"
        ):
            return "number"
        if isinstance(iterable, ast.List | ast.Tuple | ast.Set):
            kinds = {self._kind(e) for e in iterable.elts}
            return kinds.pop() if len(kinds) == 1 else "unknown"
        if isinstance(iterable, ast.Name):
            if self.kinds.get(iterable.id) == "str":
                return "str"
            values = self.values.get(iterable.id, [])
            listed = [v for v in values if isinstance(v, ast.List)]
            if listed and len(listed) == len(values):
                kinds = {self._kind(e) for v in listed for e in v.elts}
                return kinds.pop() if len(kinds) == 1 else "unknown"
        return "unknown"

    def stand_in(self, use: ast.Name, *, guess_unknown: bool = False) -> str | None:
        """The name a pupil might plausibly type instead of ``use``, or None.

        A name of unknown kind gets None, unless ``guess_unknown``: then
        another name of unknown kind stands in, else any name already set
        (Bugs wants a wrong name even at the risk of a TypeError; Parsons
        refuses, because a distractor must look like code that could run)."""
        kind = self.kinds.get(use.id, "unknown")
        if kind == "unknown" and not guess_unknown:
            return None
        scope = self.scope_of.get(use, self.tree)
        visible = dict(self.stores.get(self.tree, {}))
        if scope is not self.tree:
            visible.update(self.stores.get(scope, {}))
        # Set on an earlier line, so it already exists when this line runs.
        earlier = {
            name: max(n for n in at if n < use.lineno)
            for name, at in visible.items()
            if name != use.id and min(at) < use.lineno
        }
        same = [name for name in earlier if self.kinds.get(name, "unknown") == kind]
        if not same and kind == "unknown":
            same = list(earlier)
        # The most recently set; ties in the order the names were first set.
        return max(same, key=lambda name: earlier[name], default=None)
