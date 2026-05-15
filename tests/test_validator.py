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


def test_compile_filter_allows_lambda_as_sort_key() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            ranked = sorted(data, key=lambda item: item.get("score"))
            return ",".join([item.get("name") for item in ranked])
        """
    )

    filter_fn = compile_filter(code)

    result = filter_fn(
        [
            {"name": "b", "score": 2},
            {"name": "a", "score": 1},
            {"name": "c", "score": 3},
        ]
    )
    assert result == "a,b,c"


def test_compile_filter_allows_lambda_in_max() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            top = max(data, key=lambda item: item["age"])
            return top["name"]
        """
    )

    filter_fn = compile_filter(code)

    assert (
        filter_fn(
            [
                {"name": "alice", "age": 30},
                {"name": "bob", "age": 42},
                {"name": "carol", "age": 25},
            ]
        )
        == "bob"
    )


def test_compile_filter_lambda_body_still_validated() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            return sorted(data, key=lambda item: eval(item))
        """
    )

    with pytest.raises(FilterValidationError, match="eval"):
        compile_filter(code)


def test_compile_filter_lambda_body_blocks_dunder_attribute() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            return sorted(data, key=lambda item: item.__class__)
        """
    )

    with pytest.raises(FilterValidationError, match="Attribute access"):
        compile_filter(code)


def test_compile_filter_allows_json_round_trip() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            parsed = json.loads(data)
            return json.dumps(parsed)
        """
    )

    filter_fn = compile_filter(code)

    assert filter_fn('{"k": 1}') == '{"k": 1}'


def test_compile_filter_allows_yaml_safe_round_trip() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            parsed = yaml.safe_load(data)
            return yaml.safe_dump(parsed).strip()
        """
    )

    filter_fn = compile_filter(code)

    assert filter_fn("k: 1") == "k: 1"


def test_compile_filter_rejects_yaml_unsafe_load() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            return str(yaml.load(data))
        """
    )

    with pytest.raises(FilterValidationError, match="Method is not allowed: load"):
        compile_filter(code)


def test_compile_filter_allows_re_search_and_group() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            return re.search(r"(\\d+)", data).group(1)
        """
    )

    filter_fn = compile_filter(code)

    assert filter_fn("order #4242 received") == "4242"


def test_compile_filter_allows_re_findall_and_sub() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            numbers = re.findall(r"\\d+", data)
            cleaned = re.sub(r"\\d+", "#", data)
            return ",".join(numbers) + "|" + cleaned
        """
    )

    filter_fn = compile_filter(code)

    assert filter_fn("a1 b22 c") == "1,22|a# b# c"


def test_compile_filter_allows_nested_helper_function() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            def label(item):
                return str(item).upper()
            return ",".join([label(x) for x in data])
        """
    )

    filter_fn = compile_filter(code)

    assert filter_fn(["a", "b", "c"]) == "A,B,C"


def test_compile_filter_allows_nested_helper_with_defaults_and_kwonly() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            def render(item, prefix="-", *, suffix="!"):
                return prefix + str(item) + suffix
            return ",".join([render(x) for x in data])
        """
    )

    filter_fn = compile_filter(code)

    assert filter_fn(["a", "b"]) == "-a!,-b!"


def test_compile_filter_nested_helper_body_still_validated() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            def bad(item):
                return eval(item)
            return bad(data)
        """
    )

    with pytest.raises(FilterValidationError, match="eval"):
        compile_filter(code)


def test_compile_filter_nested_helper_blocks_dunder_attribute() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            def peek(item):
                return item.__class__
            return str(peek(data))
        """
    )

    with pytest.raises(FilterValidationError, match="Attribute access"):
        compile_filter(code)


def test_compile_filter_rejects_nested_helper_with_dunder_name() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            def __sneaky__(item):
                return str(item)
            return __sneaky__(data)
        """
    )

    with pytest.raises(FilterValidationError, match="Nested function name"):
        compile_filter(code)


def test_compile_filter_allows_re_compile_chain() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            pattern = re.compile(r"\\d+")
            return ",".join(pattern.findall(data))
        """
    )

    filter_fn = compile_filter(code)

    assert filter_fn("a1 b22 c333") == "1,22,333"


@pytest.mark.parametrize(
    ("code", "data", "expected"),
    [
        (
            """
            def filter_item(data):
                return str(math.ceil(data))
            """,
            1.2,
            "2",
        ),
        (
            """
            def filter_item(data):
                return str(statistics.mean(data))
            """,
            [1, 2, 3, 4],
            "2.5",
        ),
        (
            """
            def filter_item(data):
                return datetime.datetime.fromisoformat(data).isoformat()
            """,
            "2024-01-02T03:04:05",
            "2024-01-02T03:04:05",
        ),
        (
            """
            def filter_item(data):
                return str(datetime.datetime.now(datetime.timezone.utc).isoformat().endswith("+00:00"))
            """,
            None,
            "True",
        ),
        (
            """
            def filter_item(data):
                return str(decimal.Decimal(data).quantize(decimal.Decimal("0.01")))
            """,
            "1.2345",
            "1.23",
        ),
        (
            """
            def filter_item(data):
                c = collections.Counter(data)
                return ",".join([f"{k}:{v}" for k, v in c.most_common()])
            """,
            "abca",
            "a:2,b:1,c:1",
        ),
        (
            """
            def filter_item(data):
                return ",".join([str(x) for x in itertools.islice(data, 3)])
            """,
            [10, 20, 30, 40, 50],
            "10,20,30",
        ),
        (
            """
            def filter_item(data):
                return ",".join([str(x) for x in itertools.chain.from_iterable(data)])
            """,
            [[1, 2], [3]],
            "1,2,3",
        ),
        (
            """
            def filter_item(data):
                return str(functools.reduce(lambda a, b: a + b, data))
            """,
            [1, 2, 3, 4],
            "10",
        ),
        (
            """
            def filter_item(data):
                ranked = sorted(data, key=operator.itemgetter("v"))
                return ",".join([item["name"] for item in ranked])
            """,
            [{"name": "b", "v": 2}, {"name": "a", "v": 1}],
            "a,b",
        ),
        (
            """
            def filter_item(data):
                return textwrap.shorten(data, width=10, placeholder="...")
            """,
            "hello world here",
            "hello...",
        ),
        (
            """
            def filter_item(data):
                return html.escape(data)
            """,
            "<b>",
            "&lt;b&gt;",
        ),
        (
            """
            def filter_item(data):
                return str(base64.b64encode(data.encode("utf-8")))
            """,
            "ok",
            "b'b2s='",
        ),
        (
            """
            def filter_item(data):
                return hashlib.sha256(data.encode("utf-8")).hexdigest()[:8]
            """,
            "abc",
            "ba7816bf",
        ),
        (
            """
            def filter_item(data):
                net = ipaddress.ip_network(data)
                return str(net.supernet())
            """,
            "10.0.0.0/24",
            "10.0.0.0/23",
        ),
        (
            """
            def filter_item(data):
                return unicodedata.category(data)
            """,
            "A",
            "Lu",
        ),
        (
            """
            def filter_item(data):
                return ",".join(difflib.get_close_matches(data, ["apple", "ape", "april"], n=2))
            """,
            "appl",
            "apple,april",
        ),
    ],
)
def test_compile_filter_allows_default_stdlib_modules(
    code: str, data, expected
) -> None:
    filter_fn = compile_filter(textwrap.dedent(code))

    assert filter_fn(data) == expected


@pytest.mark.parametrize(
    "module_name",
    ["os", "sys", "subprocess", "socket", "pickle", "urllib", "shutil", "pathlib"],
)
def test_compile_filter_rejects_disallowed_modules(module_name: str) -> None:
    code = textwrap.dedent(
        f"""
        def filter_item(data):
            return {module_name}.loads(data)
        """
    )

    filter_fn = compile_filter(code)
    with pytest.raises(NameError):
        filter_fn("{}")


def test_compile_filter_rejects_operator_attrgetter() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            getter = operator.attrgetter("__class__")
            return str(getter(data))
        """
    )

    with pytest.raises(FilterValidationError, match="Method is not allowed: attrgetter"):
        compile_filter(code)


def test_compile_filter_rejects_functools_lru_cache() -> None:
    code = textwrap.dedent(
        """
        def filter_item(data):
            return str(functools.lru_cache(maxsize=1))
        """
    )

    with pytest.raises(FilterValidationError, match="Method is not allowed: lru_cache"):
        compile_filter(code)
