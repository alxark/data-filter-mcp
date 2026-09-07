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

POLICY_VERSION = "1.4"

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

SAFE_PROPERTY_READS = {
    "broadcast_address",
    "compressed",
    "exploded",
    "hostmask",
    "ip",
    "ipv4_mapped",
    "ipv6_mapped",
    "is_global",
    "is_link_local",
    "is_loopback",
    "is_multicast",
    "is_private",
    "is_reserved",
    "is_site_local",
    "is_unspecified",
    "max_prefixlen",
    "netmask",
    "network",
    "network_address",
    "num_addresses",
    "packed",
    "prefixlen",
    "reverse_pointer",
    "scope_id",
    "sixtofour",
    "teredo",
    "version",
    "with_hostmask",
    "with_netmask",
    "with_prefixlen",
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
    "address_exclude",
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
    "collapse_addresses",
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
    "get_mixed_type_key",
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
    "summarize_address_range",
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
    "v4_int_to_packed",
    "v6_int_to_packed",
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


def _source_fragment(node: ast.AST | None, max_length: int = 200) -> str | None:
    if node is None:
        return None
    try:
        fragment = ast.unparse(node)
    except Exception:
        return None
    if len(fragment) > max_length:
        return f"{fragment[: max_length - 3]}..."
    return fragment


def _node_line(node: ast.AST | None) -> int | None:
    return getattr(node, "lineno", None)


def _node_column(node: ast.AST | None) -> int | None:
    return getattr(node, "col_offset", None)


class FilterValidationError(ValueError):
    """Raised when submitted filter code breaks the policy."""

    def __init__(
        self,
        message: str,
        *,
        blocked_kind: str | None = None,
        blocked_field: str | None = None,
        blocked_value: str | None = None,
        source_fragment: str | None = None,
        source_line: int | None = None,
        source_column: int | None = None,
    ) -> None:
        self.blocked_kind = blocked_kind
        self.blocked_field = blocked_field
        self.blocked_value = blocked_value
        self.source_fragment = source_fragment
        self.source_line = source_line
        self.source_column = source_column

        details = []
        if blocked_kind is not None:
            details.append(f"blocked_kind={blocked_kind!r}")
        if blocked_field is not None:
            details.append(f"blocked_field={blocked_field!r}")
        if blocked_value is not None:
            details.append(f"blocked_value={blocked_value!r}")
        if source_fragment is not None:
            details.append(f"source_fragment={source_fragment!r}")
        if source_line is not None:
            details.append(f"source_line={source_line}")
        if source_column is not None:
            details.append(f"source_column={source_column}")

        if details:
            message = f"{message} ({', '.join(details)})"

        super().__init__(message)


class FilterValidator(ast.NodeVisitor):
    def __init__(self, module_aliases: dict[int, dict[str, str]] | None = None) -> None:
        self._module_aliases = module_aliases or {}
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
                f"{type(node).__name__} is not allowed in filter code",
                blocked_kind="disallowed_node_type",
                blocked_field="node_type",
                blocked_value=type(node).__name__,
                source_fragment=_source_fragment(node),
                source_line=_node_line(node),
                source_column=_node_column(node),
            )
        super().generic_visit(node)

    def visit_Module(self, node: ast.Module) -> None:
        if len(node.body) != 1 or not isinstance(node.body[0], ast.FunctionDef):
            raise FilterValidationError(
                "Filter code must contain exactly one top-level function definition",
                blocked_kind="invalid_module_body",
                blocked_field="top_level_nodes",
                blocked_value=str(len(node.body)),
                source_fragment=_source_fragment(node),
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.decorator_list:
            raise FilterValidationError(
                "Decorators are not allowed",
                blocked_kind="disallowed_decorator",
                blocked_field="decorator",
                blocked_value=", ".join(
                    fragment
                    for fragment in (
                        _source_fragment(decorator)
                        for decorator in node.decorator_list
                    )
                    if fragment is not None
                ),
                source_fragment=_source_fragment(node),
                source_line=_node_line(node),
                source_column=_node_column(node),
            )
        if node.returns is not None:
            raise FilterValidationError(
                "Return annotations are not allowed",
                blocked_kind="disallowed_return_annotation",
                blocked_field="return_annotation",
                blocked_value=_source_fragment(node.returns),
                source_fragment=_source_fragment(node),
                source_line=_node_line(node),
                source_column=_node_column(node),
            )

        if isinstance(self._parents.get(id(node)), ast.Module):
            if node.name != "filter_item":
                raise FilterValidationError(
                    "Filter function must be named filter_item",
                    blocked_kind="invalid_function_name",
                    blocked_field="function_name",
                    blocked_value=node.name,
                    source_fragment=_source_fragment(node),
                    source_line=_node_line(node),
                    source_column=_node_column(node),
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
                    "filter_item must have exactly one parameter named data",
                    blocked_kind="invalid_function_signature",
                    blocked_field="parameters",
                    blocked_value=self._signature_summary(args),
                    source_fragment=_source_fragment(node.args),
                    source_line=_node_line(node),
                    source_column=_node_column(node),
                )
        else:
            if node.name.startswith("__"):
                raise FilterValidationError(
                    f"Nested function name is not allowed: {node.name}",
                    blocked_kind="disallowed_nested_function_name",
                    blocked_field="function_name",
                    blocked_value=node.name,
                    source_fragment=_source_fragment(node),
                    source_line=_node_line(node),
                    source_column=_node_column(node),
                )

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in DISALLOWED_NAMES or node.id.startswith("__"):
            raise FilterValidationError(
                f"Name is not allowed: {node.id}",
                blocked_kind="disallowed_name",
                blocked_field="name",
                blocked_value=node.id,
                source_fragment=_source_fragment(node),
                source_line=_node_line(node),
                source_column=_node_column(node),
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        is_safe_dunder = node.attr in SAFE_DUNDER_ATTRIBUTES
        if node.attr.startswith("_") and not is_safe_dunder:
            raise FilterValidationError(
                f"Attribute access is not allowed: {node.attr}",
                blocked_kind="disallowed_attribute",
                blocked_field="attribute",
                blocked_value=node.attr,
                source_fragment=_source_fragment(node),
                source_line=_node_line(node),
                source_column=_node_column(node),
            )

        parent = self._parents.get(id(node))
        if self._is_safe_attribute_read(node):
            return

        is_call_target = isinstance(parent, ast.Call) and parent.func is node

        if is_safe_dunder and not is_call_target:
            self.visit(node.value)
            return

        if not is_call_target:
            if node.attr in SAFE_PROPERTY_READS:
                self.visit(node.value)
                return
            raise FilterValidationError(
                "Attribute access is restricted to approved method calls",
                blocked_kind="disallowed_attribute_read",
                blocked_field="attribute",
                blocked_value=node.attr,
                source_fragment=_source_fragment(node),
                source_line=_node_line(node),
                source_column=_node_column(node),
            )
        if node.attr not in SAFE_METHODS:
            raise FilterValidationError(
                f"Method is not allowed: {node.attr}",
                blocked_kind="disallowed_method",
                blocked_field="method",
                blocked_value=node.attr,
                source_fragment=_source_fragment(node),
                source_line=_node_line(node),
                source_column=_node_column(node),
            )

        self.visit(node.value)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if (
                node.func.id not in SAFE_BUILTINS
                and node.func.id not in self._defined_function_names
            ):
                blocked_kind = (
                    "disallowed_name"
                    if node.func.id in DISALLOWED_NAMES
                    or node.func.id.startswith("__")
                    else "disallowed_function"
                )
                blocked_node = node.func if blocked_kind == "disallowed_name" else node
                raise FilterValidationError(
                    f"Calling this function is not allowed: {node.func.id}",
                    blocked_kind=blocked_kind,
                    blocked_field=(
                        "name" if blocked_kind == "disallowed_name" else "function"
                    ),
                    blocked_value=node.func.id,
                    source_fragment=_source_fragment(blocked_node),
                    source_line=_node_line(blocked_node),
                    source_column=_node_column(blocked_node),
                )
            self.visit(node.func)
        elif isinstance(node.func, ast.Attribute):
            self.visit(node.func)
        else:
            raise FilterValidationError(
                "Only whitelisted function calls are allowed",
                blocked_kind="disallowed_call_target",
                blocked_field="function",
                blocked_value=_source_fragment(node.func) or type(node.func).__name__,
                source_fragment=_source_fragment(node),
                source_line=_node_line(node),
                source_column=_node_column(node),
            )

        for arg in node.args:
            if isinstance(arg, ast.Starred):
                raise FilterValidationError(
                    "Starred arguments are not allowed",
                    blocked_kind="disallowed_argument",
                    blocked_field="argument",
                    blocked_value=_source_fragment(arg),
                    source_fragment=_source_fragment(node),
                    source_line=_node_line(arg),
                    source_column=_node_column(arg),
                )
            self.visit(arg)

        for keyword in node.keywords:
            if keyword.arg is None:
                raise FilterValidationError(
                    "Double-star keyword arguments are not allowed",
                    blocked_kind="disallowed_keyword_argument",
                    blocked_field="keyword",
                    blocked_value="**",
                    source_fragment=_source_fragment(node),
                    source_line=_node_line(keyword.value),
                    source_column=_node_column(keyword.value),
                )
            self.visit(keyword)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        if node.is_async:
            raise FilterValidationError(
                "Async comprehensions are not allowed",
                blocked_kind="disallowed_async_comprehension",
                blocked_field="is_async",
                blocked_value=str(node.is_async),
                source_fragment=_source_fragment(node),
            )
        self.generic_visit(node)

    @staticmethod
    def _signature_summary(args: ast.arguments) -> str:
        positional = [arg.arg for arg in args.args]
        keyword_only = [arg.arg for arg in args.kwonlyargs]
        vararg = args.vararg.arg if args.vararg is not None else None
        kwarg = args.kwarg.arg if args.kwarg is not None else None
        return (
            f"args={positional!r}, vararg={vararg!r}, "
            f"kwonlyargs={keyword_only!r}, kwarg={kwarg!r}, "
            f"defaults={len(args.defaults)}, kw_defaults={len(args.kw_defaults)}"
        )

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
        if path:
            scope: ast.AST | None = node
            while scope is not None:
                aliases = self._module_aliases.get(id(scope), {})
                if path[0] in aliases:
                    path = (aliases[path[0]], *path[1:])
                    break
                scope = self._parents.get(id(scope))
        return path in SAFE_ATTRIBUTE_READS


class _ImportStripper(ast.NodeTransformer):
    """Remove redundant imports without executing Python's import machinery."""

    def __init__(self) -> None:
        self.module_aliases: dict[int, dict[str, str]] = {}
        self._scope_aliases: dict[str, str] = {}
        self.global_aliases: dict[str, Any] = {}

    def visit_Module(self, node: ast.Module) -> ast.Module:
        self.module_aliases[id(node)] = self._scope_aliases
        body: list[ast.stmt] = []
        for statement in node.body:
            if isinstance(statement, ast.Import):
                self._check_import(statement)
                for alias in statement.names:
                    if alias.asname:
                        self.global_aliases[alias.asname] = SAFE_MODULES[alias.name]
            else:
                body.append(statement)
        node.body = body
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        outer_aliases = self._scope_aliases
        self._scope_aliases = {}
        self.module_aliases[id(node)] = self._scope_aliases
        try:
            self.generic_visit(node)
        finally:
            self._scope_aliases = outer_aliases
        return node

    def _check_import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name not in SAFE_MODULES:
                self._reject_import(node, alias.name)
            if alias.asname:
                # Reuse the existing name restrictions even for removed imports.
                FilterValidator().visit(ast.copy_location(
                    ast.Name(id=alias.asname, ctx=ast.Store()), node
                ))
                if alias.asname != alias.name:
                    self._scope_aliases[alias.asname] = alias.name

    def visit_Import(self, node: ast.Import) -> ast.stmt | list[ast.stmt]:
        self._check_import(node)
        replacements: list[ast.stmt] = []
        for alias in node.names:
            if alias.asname and alias.asname != alias.name:
                replacements.append(ast.copy_location(ast.Assign(
                    targets=[ast.Name(id=alias.asname, ctx=ast.Store())],
                    value=ast.Name(id=alias.name, ctx=ast.Load()),
                ), node))
        # A no-op keeps all statement suites valid, including try/finally.
        return replacements or ast.copy_location(ast.Pass(), node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._reject_import(node, "." * node.level + (node.module or ""))

    @staticmethod
    def _reject_import(node: ast.AST, module_name: str) -> None:
        raise FilterValidationError(
            f"Import of module is not allowed: {module_name}",
            blocked_kind="disallowed_import",
            blocked_field="module",
            blocked_value=module_name,
            source_fragment=_source_fragment(node),
            source_line=_node_line(node),
            source_column=_node_column(node),
        )


def _parse_filter(source_code: str) -> ast.Module:
    try:
        return ast.parse(source_code, mode="exec")
    except SyntaxError as exc:
        raise FilterValidationError(
            f"Invalid Python syntax: {exc.msg}",
            blocked_kind="invalid_syntax",
            blocked_field="syntax",
            blocked_value=exc.msg,
            source_fragment=(exc.text or "").strip() or None,
            source_line=exc.lineno,
            source_column=exc.offset,
        ) from exc


def _compile_tree(tree: ast.Module) -> CodeType:
    return compile(tree, filename="<filter>", mode="exec")


def compile_filter(source_code: str):
    tree = _parse_filter(source_code)
    stripper = _ImportStripper()
    tree = ast.fix_missing_locations(stripper.visit(tree))
    FilterValidator(stripper.module_aliases).validate(tree)
    compiled = _compile_tree(tree)

    execution_globals: dict[str, Any] = {
        "__builtins__": SAFE_BUILTINS.copy(),
        **SAFE_MODULES,
        **stripper.global_aliases,
    }
    exec(compiled, execution_globals, execution_globals)

    filter_fn = execution_globals.get("filter_item")
    if not callable(filter_fn):
        raise FilterValidationError(
            "filter_item was not created successfully",
            blocked_kind="missing_filter_function",
            blocked_field="function_name",
            blocked_value="filter_item",
        )

    return filter_fn
