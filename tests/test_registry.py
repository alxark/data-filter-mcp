from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from data_filter_mcp.registry import (
    FilterExpiredError,
    FilterNotFoundError,
    FilterRegistry,
)


def test_registry_returns_registered_filter() -> None:
    current_time = {"value": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    registry = FilterRegistry(
        filter_ttl_seconds=30,
        cleanup_interval_seconds=30.0,
        now_provider=lambda: current_time["value"],
    )

    entry = registry.register(
        source_code="def filter_item(data):\n    return 'ok'\n",
        function=lambda data: "ok",
        policy_version="1.0",
    )

    assert registry.get(entry.filter_id).filter_id == entry.filter_id
    assert len(registry) == 1


def test_registry_evicts_expired_filter_on_access() -> None:
    current_time = {"value": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    registry = FilterRegistry(
        filter_ttl_seconds=5,
        cleanup_interval_seconds=30.0,
        now_provider=lambda: current_time["value"],
    )

    entry = registry.register(
        source_code="def filter_item(data):\n    return 'ok'\n",
        function=lambda data: "ok",
        policy_version="1.0",
    )
    current_time["value"] = current_time["value"] + timedelta(seconds=6)

    with pytest.raises(FilterExpiredError, match="expired"):
        registry.get(entry.filter_id)

    with pytest.raises(FilterNotFoundError, match="Unknown filter_id"):
        registry.get(entry.filter_id)


def test_registry_cleanup_removes_expired_entries() -> None:
    current_time = {"value": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    registry = FilterRegistry(
        filter_ttl_seconds=5,
        cleanup_interval_seconds=30.0,
        now_provider=lambda: current_time["value"],
    )

    registry.register(
        source_code="def filter_item(data):\n    return 'ok'\n",
        function=lambda data: "ok",
        policy_version="1.0",
    )
    current_time["value"] = current_time["value"] + timedelta(seconds=10)

    assert registry.cleanup_expired() == 1
    assert len(registry) == 0
