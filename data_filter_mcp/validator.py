from __future__ import annotations

import ast
import json
import re
from types import CodeType
from typing import Any

import yaml

POLICY_VERSION = "1.2"

SAFE_MODULES: dict[str, Any] = {
    "json": json,
    "yaml": yaml,
    "re": re,
}

SAFE_BUILTINS: dict[str, Any] = {
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

SAFE_METHODS = {
    "append",
    "capitalize",
    "casefold",
    "center",
    "compile",
    "count",
    "dumps",
    "encode",
    "end",
    "endswith",
    "escape",
    "expandtabs",
    "extend",
    "find",
    "findall",
    "fullmatch",
    "get",
    "group",
    "groupdict",
    "groups",
    "index",
    "isalnum",
    "isalpha",
    "isascii",
    "isdecimal",
    "isdigit",
    "isidentifier",
    "islower",
    "isnumeric",
    "isprintable",
    "isspace",
    "istitle",
    "isupper",
    "items",
    "join",
    "keys",
    "ljust",
    "loads",
    "lower",
    "lstrip",
    "maketrans",
    "match",
    "partition",
    "removeprefix",
    "removesuffix",
    "replace",
    "rfind",
    "rindex",
    "rjust",
    "rpartition",
    "rsplit",
    "rstrip",
    "safe_dump",
    "safe_load",
    "search",
    "span",
    "split",
    "splitlines",
    "start",
    "startswith",
    "strip",
    "sub",
    "subn",
    "swapcase",
    "title",
    "translate",
    "upper",
    "values",
    "zfill",
}

DISALLOWED_NAMES = {
    "__builtins__",
    "__import__",
    "eval",
    "exec",
    "globals",
    "locals",
    "open",
}

ALLOWED_NODE_TYPES = {
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.Assign,
    ast.AugAssign,
    ast.For,
    ast.While,
    ast.If,
    ast.Pass,
    ast.Expr,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.Set,
    ast.Dict,
    ast.Subscript,
    ast.Slice,
    ast.Compare,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.IfExp,
    ast.Lambda,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.Attribute,
    ast.JoinedStr,
    ast.FormattedValue,
    ast.keyword,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.And,
    ast.Or,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.Eq,
    ast.NotEq,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.In,
    ast.NotIn,
    ast.Is,
    ast.IsNot,
}


class FilterValidationError(ValueError):
    """Raised when submitted filter code breaks the policy."""


class FilterValidator(ast.NodeVisitor):
    def __init__(self) -> None:
        self._parents: dict[int, ast.AST] = {}

    def validate(self, tree: ast.AST) -> None:
        self._parents = self._build_parent_map(tree)
        self.visit(tree)

    def generic_visit(self, node: ast.AST) -> None:
        if type(node) not in ALLOWED_NODE_TYPES:
            raise FilterValidationError(
                f"{type(node).__name__} is not allowed in filter code"
            )
        super().generic_visit(node)

    def visit_Module(self, node: ast.Module) -> None:
        if len(node.body) != 1 or not isinstance(node.body[0], ast.FunctionDef):
            raise FilterValidationError(
                "Filter code must contain exactly one top-level function definition"
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name != "filter_item":
            raise FilterValidationError("Filter function must be named filter_item")
        if node.decorator_list:
            raise FilterValidationError("Decorators are not allowed")
        if node.returns is not None:
            raise FilterValidationError("Return annotations are not allowed")

        args = node.args
        if (
            len(args.args) != 1
            or args.args[0].arg != "data"
            or args.vararg is not None
            or args.kwarg is not None
            or args.kwonlyargs
            or args.defaults
            or args.kw_defaults
        ):
            raise FilterValidationError(
                "filter_item must have exactly one parameter named data"
            )

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in DISALLOWED_NAMES or node.id.startswith("__"):
            raise FilterValidationError(f"Name is not allowed: {node.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            raise FilterValidationError(f"Attribute access is not allowed: {node.attr}")

        parent = self._parents.get(id(node))
        if not isinstance(parent, ast.Call) or parent.func is not node:
            raise FilterValidationError(
                "Attribute access is restricted to approved method calls"
            )
        if node.attr not in SAFE_METHODS:
            raise FilterValidationError(f"Method is not allowed: {node.attr}")

        self.visit(node.value)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id not in SAFE_BUILTINS:
                raise FilterValidationError(
                    f"Calling this function is not allowed: {node.func.id}"
                )
            self.visit(node.func)
        elif isinstance(node.func, ast.Attribute):
            self.visit(node.func)
        else:
            raise FilterValidationError("Only whitelisted function calls are allowed")

        for arg in node.args:
            if isinstance(arg, ast.Starred):
                raise FilterValidationError("Starred arguments are not allowed")
            self.visit(arg)

        for keyword in node.keywords:
            if keyword.arg is None:
                raise FilterValidationError(
                    "Double-star keyword arguments are not allowed"
                )
            self.visit(keyword)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        if node.is_async:
            raise FilterValidationError("Async comprehensions are not allowed")
        self.generic_visit(node)

    @staticmethod
    def _build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
        parents: dict[int, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[id(child)] = parent
        return parents


def _parse_filter(source_code: str) -> ast.Module:
    try:
        return ast.parse(source_code, mode="exec")
    except SyntaxError as exc:
        raise FilterValidationError(f"Invalid Python syntax: {exc.msg}") from exc


def _compile_tree(tree: ast.Module) -> CodeType:
    return compile(tree, filename="<filter>", mode="exec")


def compile_filter(source_code: str):
    tree = _parse_filter(source_code)
    FilterValidator().validate(tree)
    compiled = _compile_tree(tree)

    execution_globals: dict[str, Any] = {
        "__builtins__": SAFE_BUILTINS.copy(),
        **SAFE_MODULES,
    }
    exec(compiled, execution_globals, execution_globals)

    filter_fn = execution_globals.get("filter_item")
    if not callable(filter_fn):
        raise FilterValidationError("filter_item was not created successfully")

    return filter_fn
