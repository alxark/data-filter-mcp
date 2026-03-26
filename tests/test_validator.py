from __future__ import annotations

import textwrap

import pytest

from data_filter_mcp.validator import FilterValidationError, compile_filter


def test_compile_filter_accepts_valid_code() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            lines = [str(item) for item in data]
            return "\\n".join(lines)
        """
    )

    filter_fn = compile_filter(code)

    assert filter_fn([1, 2, 3]) == "1\n2\n3"


def test_compile_filter_allows_safe_method_calls() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            return data.get("name", "").upper()
        """
    )

    filter_fn = compile_filter(code)

    assert filter_fn({"name": "alice"}) == "ALICE"


@pytest.mark.parametrize(
    ("code", "data", "expected"),
    [
        (
            """
            def filter_item(data):
                return str(data.count("l"))
            """,
            "hello",
            "2",
        ),
        (
            """
            def filter_item(data):
                return str(data.find("lo"))
            """,
            "hello",
            "3",
        ),
        (
            """
            def filter_item(data):
                return data.removeprefix("pre-").removesuffix("-post")
            """,
            "pre-value-post",
            "value",
        ),
        (
            """
            def filter_item(data):
                left, middle, right = data.partition(":")
                return "|".join([left, middle, right])
            """,
            "key:value",
            "key|:|value",
        ),
        (
            """
            def filter_item(data):
                table = str.maketrans({"a": "o"})
                return data.translate(table)
            """,
            "banana",
            "bonono",
        ),
        (
            """
            def filter_item(data):
                return str(data.isidentifier())
            """,
            "user_name",
            "True",
        ),
        (
            """
            def filter_item(data):
                return data.swapcase().center(7, "-")
            """,
            "Ab",
            "---aB--",
        ),
    ],
)
def test_compile_filter_allows_extended_string_methods(
    code: str, data: str, expected: str
) -> None:
    filter_fn = compile_filter(textwrap.dedent(code))

    assert filter_fn(data) == expected


def test_compile_filter_rejects_extra_top_level_nodes() -> None:
    code = textwrap.dedent(
        """
        value = 1

        def filter_item(data):
            return "ok"
        """
    )

    with pytest.raises(FilterValidationError, match="exactly one top-level function"):
        compile_filter(code)


def test_compile_filter_rejects_imports() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            import os
            return "nope"
        """
    )

    with pytest.raises(FilterValidationError, match="Import"):
        compile_filter(code)


def test_compile_filter_rejects_attribute_reads() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            return str(data.__class__)
        """
    )

    with pytest.raises(FilterValidationError, match="Attribute access"):
        compile_filter(code)


def test_compile_filter_rejects_string_format_methods() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            return "{0.__class__}".format(data)
        """
    )

    with pytest.raises(FilterValidationError, match="Method is not allowed: format"):
        compile_filter(code)


def test_compile_filter_requires_exact_signature() -> None:
    code = textwrap.dedent(
        """
        def filter_item(item, extra):
            return "bad"
        """
    )

    with pytest.raises(FilterValidationError, match="exactly one parameter named data"):
        compile_filter(code)
