from __future__ import annotations

import ast
import base64
import collections
import datetime
import decimal
import difflib
import functools
import hashlib
import html
import ipaddress
import itertools
import json
import math
import operator
import re
import statistics
import textwrap
import unicodedata
from types import CodeType
from typing import Any

import yaml

POLICY_VERSION = "1.3"

SAFE_MODULES: dict[str, Any] = {
    "base64": base64,
    "collections": collections,
    "datetime": datetime,
    "decimal": decimal,
    "difflib": difflib,
    "functools": functools,
    "hashlib": hashlib,
    "html": html,
    "ipaddress": ipaddress,
    "itertools": itertools,
    "json": json,
    "math": math,
    "operator": operator,
    "re": re,
    "statistics": statistics,
    "textwrap": textwrap,
    "unicodedata": unicodedata,
    "yaml": yaml,
}

SAFE_ATTRIBUTE_READS = {
    ("datetime", "date"),
    ("datetime", "datetime"),
    ("datetime", "time"),
    ("datetime", "timedelta"),
    ("datetime", "timezone"),
    ("datetime", "timezone", "utc"),
    ("itertools", "chain"),
}

SAFE_DUNDER_ATTRIBUTES = {
    "__name__",
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
    "set": set,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "isinstance": isinstance,
    "Exception": Exception,
}

SAFE_METHODS = {
    "IPv4Address",
    "IPv4Network",
    "IPv6Address",
    "IPv6Network",
    "Decimal",
    "OrderedDict",
    "SequenceMatcher",
    "append",
    "appendleft",
    "abs",
    "accumulate",
    "add",
    "astimezone",
    "b16decode",
    "b16encode",
    "b32decode",
    "b32encode",
    "b64decode",
    "b64encode",
    "bidirectional",
    "blake2b",
    "blake2s",
    "capitalize",
    "casefold",
    "category",
    "center",
    "ceil",
    "chain",
    "ChainMap",
    "cmp_to_key",
    "comb",
    "combinations",
    "combinations_with_replacement",
    "combine",
    "combining",
    "compile",
    "compress",
    "context_diff",
    "copysign",
    "copy",
    "copy_sign",
    "count",
    "Counter",
    "cycle",
    "date",
    "Decimal",
    "decimal",
    "dedent",
    "degrees",
    "deque",
    "digit",
    "digest",
    "dumps",
    "dropwhile",
    "encode",
    "end",
    "endswith",
    "elements",
    "eq",
    "escape",
    "exp",
    "expandtabs",
    "extend",
    "extendleft",
    "fabs",
    "factorial",
    "fill",
    "filterfalse",
    "find",
    "findall",
    "floor",
    "floordiv",
    "fmean",
    "fmod",
    "from_iterable",
    "fromisoformat",
    "fromkeys",
    "fromordinal",
    "fromtimestamp",
    "fullmatch",
    "gcd",
    "ge",
    "geometric_mean",
    "get",
    "get_close_matches",
    "get_matching_blocks",
    "get_opcodes",
    "group",
    "groupdict",
    "groups",
    "groupby",
    "gt",
    "harmonic_mean",
    "hexdigest",
    "hosts",
    "hypot",
    "index",
    "indent",
    "ip_address",
    "ip_interface",
    "ip_network",
    "isalnum",
    "isalpha",
    "isascii",
    "is_finite",
    "is_infinite",
    "is_nan",
    "isclose",
    "isdecimal",
    "isdigit",
    "isidentifier",
    "isfinite",
    "isinf",
    "isoformat",
    "islower",
    "islice",
    "isnan",
    "isnumeric",
    "isprintable",
    "isspace",
    "istitle",
    "isupper",
    "isoweekday",
    "items",
    "itemgetter",
    "join",
    "keys",
    "lcm",
    "le",
    "ljust",
    "log",
    "log10",
    "log2",
    "loads",
    "lower",
    "lstrip",
    "lt",
    "maketrans",
    "match",
    "md5",
    "mean",
    "median",
    "median_high",
    "median_low",
    "mirrored",
    "mod",
    "mode",
    "modf",
    "most_common",
    "move_to_end",
    "mul",
    "multimode",
    "name",
    "namedtuple",
    "ndiff",
    "ne",
    "neg",
    "new",
    "normalize",
    "now",
    "numeric",
    "overlaps",
    "partition",
    "partial",
    "perm",
    "permutations",
    "pop",
    "popleft",
    "pos",
    "pow",
    "product",
    "pstdev",
    "push",
    "pvariance",
    "quantiles",
    "quantize",
    "quick_ratio",
    "radians",
    "ratio",
    "real_quick_ratio",
    "reduce",
    "removeprefix",
    "removesuffix",
    "remainder",
    "replace",
    "repeat",
    "rfind",
    "rindex",
    "rjust",
    "rpartition",
    "rsplit",
    "rstrip",
    "safe_dump",
    "safe_load",
    "search",
    "setdefault",
    "sha1",
    "sha224",
    "sha256",
    "sha384",
    "sha512",
    "shorten",
    "sort",
    "span",
    "split",
    "splitlines",
    "start",
    "startswith",
    "starmap",
    "stdev",
    "strftime",
    "strip",
    "sub",
    "subnet_of",
    "subnets",
    "subn",
    "subtract",
    "supernet",
    "supernet_of",
    "swapcase",
    "takewhile",
    "tee",
    "title",
    "timestamp",
    "time",
    "today",
    "to_eng_string",
    "to_integral_value",
    "total_seconds",
    "translate",
    "truediv",
    "trunc",
    "unescape",
    "unified_diff",
    "upper",
    "update",
    "urlsafe_b64decode",
    "urlsafe_b64encode",
    "utcfromtimestamp",
    "utcnow",
    "values",
    "variance",
    "weekday",
    "wrap",
    "wraps",
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
    ast.Try,
    ast.ExceptHandler,
    ast.Set,
    ast.Dict,
    ast.Subscript,
    ast.Slice,
    ast.Compare,
    ast.BoolOp,
    ast.Continue,
    ast.Break,
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
        self._defined_function_names: set[str] = set()

    def validate(self, tree: ast.AST) -> None:
        self._parents = self._build_parent_map(tree)
        self._defined_function_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
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
        if node.decorator_list:
            raise FilterValidationError("Decorators are not allowed")
        if node.returns is not None:
            raise FilterValidationError("Return annotations are not allowed")

        if isinstance(self._parents.get(id(node)), ast.Module):
            if node.name != "filter_item":
                raise FilterValidationError(
                    "Filter function must be named filter_item"
                )

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
        else:
            if node.name.startswith("__"):
                raise FilterValidationError(
                    f"Nested function name is not allowed: {node.name}"
                )

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in DISALLOWED_NAMES or node.id.startswith("__"):
            raise FilterValidationError(f"Name is not allowed: {node.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        is_safe_dunder = node.attr in SAFE_DUNDER_ATTRIBUTES
        if node.attr.startswith("_") and not is_safe_dunder:
            raise FilterValidationError(f"Attribute access is not allowed: {node.attr}")

        parent = self._parents.get(id(node))
        if self._is_safe_attribute_read(node):
            return

        is_call_target = isinstance(parent, ast.Call) and parent.func is node

        if is_safe_dunder and not is_call_target:
            self.visit(node.value)
            return

        if not is_call_target:
            raise FilterValidationError(
                "Attribute access is restricted to approved method calls"
            )
        if node.attr not in SAFE_METHODS:
            raise FilterValidationError(f"Method is not allowed: {node.attr}")

        self.visit(node.value)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if (
                node.func.id not in SAFE_BUILTINS
                and node.func.id not in self._defined_function_names
            ):
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

    @staticmethod
    def _attribute_path(node: ast.Attribute) -> tuple[str, ...] | None:
        parts: list[str] = []
        current: ast.AST = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Name):
            return None
        parts.append(current.id)
        return tuple(reversed(parts))

    def _is_safe_attribute_read(self, node: ast.Attribute) -> bool:
        parent = self._parents.get(id(node))
        if isinstance(parent, ast.Call) and parent.func is node:
            return False
        path = self._attribute_path(node)
        return path in SAFE_ATTRIBUTE_READS


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
