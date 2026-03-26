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
