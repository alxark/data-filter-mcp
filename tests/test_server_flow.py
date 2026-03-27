from __future__ import annotations

import json
import textwrap
from datetime import datetime, timedelta, timezone

import pytest

from data_filter_mcp.server import FilterService
from data_filter_mcp.validator import POLICY_VERSION


def test_filter_service_registers_and_runs_json_filter(tmp_path) -> None:
    service = FilterService(filter_ttl_seconds=300, cleanup_interval_seconds=300.0)
    code = textwrap.dedent(
        """
        def filter_item(data):
            lines = [f"- {item}" for item in data["items"]]
            return "\\n".join(lines)
        """
    )
    file_path = tmp_path / "items.json"
    file_path.write_text(json.dumps({"items": ["red", "blue"]}), encoding="utf-8")

    register_result = service.register_filter(code)
    run_result = service.run_filter(register_result.filter_id, str(file_path))

    assert register_result.policy_version == POLICY_VERSION
    assert register_result.ttl_seconds == 300
    assert run_result.file_type == "json"
    assert run_result.result_text == "- red\n- blue"


def test_filter_service_requires_text_result(tmp_path) -> None:
    service = FilterService(filter_ttl_seconds=300, cleanup_interval_seconds=300.0)
    code = textwrap.dedent(
        """
        def filter_item(data):
            return data
        """
    )
    file_path = tmp_path / "items.json"
    file_path.write_text(json.dumps({"items": ["red", "blue"]}), encoding="utf-8")

    register_result = service.register_filter(code)

    with pytest.raises(ValueError, match="must return a string"):
        service.run_filter(register_result.filter_id, str(file_path))


def test_filter_service_allows_file_inside_workdir(tmp_path) -> None:
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    file_path = allowed_dir / "data.json"
    file_path.write_text(json.dumps({"v": 1}), encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(allowed_dir)],
    )
    code = textwrap.dedent(
        """
        def filter_item(data):
            return str(data["v"])
        """
    )
    reg = service.register_filter(code)
    result = service.run_filter(reg.filter_id, str(file_path))
    assert result.result_text == "1"


def test_filter_service_rejects_file_outside_workdir(tmp_path) -> None:
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    file_path = outside_dir / "secret.json"
    file_path.write_text(json.dumps({"x": 1}), encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(allowed_dir)],
    )
    code = textwrap.dedent(
        """
        def filter_item(data):
            return "ok"
        """
    )
    reg = service.register_filter(code)
    with pytest.raises(ValueError, match="outside allowed workdirs"):
        service.run_filter(reg.filter_id, str(file_path))


def test_filter_service_rejects_relative_file_path(tmp_path) -> None:
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    file_path = allowed_dir / "data.json"
    file_path.write_text(json.dumps({"x": 1}), encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(allowed_dir)],
    )
    code = textwrap.dedent(
        """
        def filter_item(data):
            return "ok"
        """
    )
    reg = service.register_filter(code)
    with pytest.raises(ValueError, match="must be an absolute path"):
        service.run_filter(reg.filter_id, "relative/path.json")


def test_filter_service_rejects_relative_workdir() -> None:
    with pytest.raises(ValueError, match="must be an absolute path"):
        FilterService(
            filter_ttl_seconds=300,
            cleanup_interval_seconds=300.0,
            workdirs=["relative/dir"],
        )


def test_filter_service_rejects_nonexistent_workdir(tmp_path) -> None:
    bogus = tmp_path / "does_not_exist"
    with pytest.raises(ValueError, match="not an existing directory"):
        FilterService(
            filter_ttl_seconds=300,
            cleanup_interval_seconds=300.0,
            workdirs=[str(bogus)],
        )


def test_filter_service_no_workdirs_allows_any_file(tmp_path) -> None:
    file_path = tmp_path / "anywhere.json"
    file_path.write_text(json.dumps({"k": "v"}), encoding="utf-8")

    service = FilterService(filter_ttl_seconds=300, cleanup_interval_seconds=300.0)
    code = textwrap.dedent(
        """
        def filter_item(data):
            return data["k"]
        """
    )
    reg = service.register_filter(code)
    result = service.run_filter(reg.filter_id, str(file_path))
    assert result.result_text == "v"


def test_filter_service_multiple_workdirs(tmp_path) -> None:
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    dir_b = tmp_path / "b"
    dir_b.mkdir()
    file_a = dir_a / "a.json"
    file_a.write_text(json.dumps({"src": "a"}), encoding="utf-8")
    file_b = dir_b / "b.json"
    file_b.write_text(json.dumps({"src": "b"}), encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(dir_a), str(dir_b)],
    )
    code = textwrap.dedent(
        """
        def filter_item(data):
            return data["src"]
        """
    )
    reg = service.register_filter(code)
    assert service.run_filter(reg.filter_id, str(file_a)).result_text == "a"
    assert service.run_filter(reg.filter_id, str(file_b)).result_text == "b"


def test_filter_service_rejects_expired_filters(tmp_path) -> None:
    current_time = {"value": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    service = FilterService(
        filter_ttl_seconds=5,
        cleanup_interval_seconds=30.0,
        now_provider=lambda: current_time["value"],
    )
    code = textwrap.dedent(
        """
        def filter_item(data):
            return "ok"
        """
    )
    file_path = tmp_path / "items.txt"
    file_path.write_text("one\ntwo\n", encoding="utf-8")

    register_result = service.register_filter(code)
    current_time["value"] = current_time["value"] + timedelta(seconds=6)

    with pytest.raises(ValueError, match="expired"):
        service.run_filter(register_result.filter_id, str(file_path))
