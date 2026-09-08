from __future__ import annotations

import dis
import textwrap
from types import CodeType

import pytest

from data_filter_mcp.server import FilterService
from data_filter_mcp.validator import SAFE_MODULES, FilterValidationError, compile_filter


@pytest.mark.parametrize("module", SAFE_MODULES)
@pytest.mark.parametrize("location", ["top", "body"])
def test_preloaded_imports(module, location):
    statement = f"import {module}"
    code = (f"{statement}\ndef filter_item(data):\n    return {module}.__name__"
            if location == "top" else
            f"def filter_item(data):\n    {statement}\n    return {module}.__name__")
    assert compile_filter(code)(None) == module


@pytest.mark.parametrize("location", ["top", "body"])
@pytest.mark.parametrize("statement, expression, expected", [
    ("import math, statistics", "str(math.floor(statistics.mean(data)))", "2"),
    ("import datetime as dt", 'dt.datetime.fromisoformat("2024-01-02").isoformat()',
     "2024-01-02T00:00:00"),
    ("import math as m, json as j", "j.dumps(m.ceil(1.2))", "2"),
    ("import math as math", "str(math.ceil(1.2))", "2"),
])
def test_aliases_and_multiple_imports(location, statement, expression, expected):
    code = (f"{statement}\ndef filter_item(data):\n    return {expression}"
            if location == "top" else
            f"def filter_item(data):\n    {statement}\n    return {expression}")
    assert compile_filter(code)([1, 2, 4]) == expected


@pytest.mark.parametrize("statement", [
    "import os", "import math, os", "import os.path", "import json.tool",
    "from math import ceil", "from math import *", "from . import x",
    "from os import path",
])
@pytest.mark.parametrize("location", ["top", "body"])
def test_rejected_imports(statement, location):
    code = (f"{statement}\ndef filter_item(data):\n    return 'ok'"
            if location == "top" else
            f"def filter_item(data):\n    {statement}\n    return 'ok'")
    with pytest.raises(FilterValidationError) as error:
        compile_filter(code)
    assert error.value.blocked_kind == "disallowed_import"
    assert error.value.source_fragment == statement
    assert error.value.source_line == (1 if location == "top" else 2)


@pytest.mark.parametrize("alias", ["eval", "__builtins__", "__import__", "open"])
@pytest.mark.parametrize("location", ["top", "body"])
def test_alias_names_are_validated(alias, location):
    statement = f"import math as {alias}"
    code = (f"{statement}\ndef filter_item(data):\n    return 'ok'"
            if location == "top" else
            f"def filter_item(data):\n    {statement}\n    return 'ok'")
    with pytest.raises(FilterValidationError) as error:
        compile_filter(code)
    assert error.value.blocked_kind == "disallowed_name"
    assert error.value.blocked_value == alias


@pytest.mark.parametrize("code", [
    "import math",
    "import math as m",
    "import math\nx = 1\ndef filter_item(data):\n    return 'ok'",
    "import math\ndef filter_item(data):\n    pass\ndef other():\n    pass",
])
def test_top_level_constraints_remain(code):
    with pytest.raises(FilterValidationError, match="exactly one top-level function"):
        compile_filter(code)


def test_empty_suites_and_nested_helpers():
    code = textwrap.dedent('''\
        import math
        def filter_item(data):
            def helper(x):
                import math as m
                return m.ceil(x)
            if data:
                import math
            else:
                import json
            for item in []:
                import re
            try:
                import math
            except Exception:
                import json
            finally:
                import re
            return str(helper(data))
    ''')
    function = compile_filter(code)
    assert function(16) == "16"


    def assert_no_imports(code):
        assert not any(instruction.opname.startswith("IMPORT_")
                       for instruction in dis.get_instructions(code))
        for constant in code.co_consts:
            if isinstance(constant, CodeType):
                assert_no_imports(constant)

    assert_no_imports(function.__code__)


def test_remaining_code_is_validated_with_original_line_numbers():
    with pytest.raises(FilterValidationError) as error:
        compile_filter("import math\ndef filter_item(data):\n    import json\n    return eval(data)")
    assert error.value.blocked_value == "eval"
    assert error.value.source_line == 4


def test_alias_does_not_allow_unsafe_methods():
    with pytest.raises(FilterValidationError, match="Method is not allowed: load"):
        compile_filter("import yaml as y\ndef filter_item(data):\n    return y.load(data)")


def test_aliases_in_sibling_helpers_do_not_collide():
    function = compile_filter(textwrap.dedent('''\
        def filter_item(data):
            def first(value):
                import datetime as m
                return m.datetime.fromisoformat(value).isoformat()
            def second(value):
                import math as m
                return str(m.ceil(value))
            return first("2024-01-02") + second(1.2)
    '''))
    assert function(None) == "2024-01-02T00:00:002"


def test_helper_alias_does_not_leak_into_parent_validation():
    with pytest.raises(FilterValidationError, match="Attribute access is restricted"):
        compile_filter(textwrap.dedent('''\
            def filter_item(data):
                def helper(value):
                    import datetime as dt
                    return dt.datetime.fromisoformat(value).isoformat()
                dt = data
                return str(dt.date)
        '''))


def test_service_runs_and_converts_filter_with_imports(tmp_path):
    service = FilterService(workdirs=[str(tmp_path)])
    source = tmp_path / "input.txt"
    destination = tmp_path / "output.txt"
    source.write_text("red\nblue\n", encoding="utf-8")
    registered = service.register_filter(
        "import json as j\ndef filter_item(data):\n    import math\n    return j.dumps(math.ceil(len(data) / 2))"
    )
    assert registered.policy_version == "1.5"
    assert service.run_filter(registered.filter_id, str(source)).result_text == "1"
    service.convert_file(registered.filter_id, str(source), str(destination))
    assert destination.read_text(encoding="utf-8") == "1"
