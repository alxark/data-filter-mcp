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


def test_filter_service_converts_json_file_to_destination(tmp_path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    source = workdir / "items.json"
    destination = workdir / "out" / "items.txt"
    source.write_text(json.dumps({"items": ["red", "blue"]}), encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(workdir)],
    )
    code = textwrap.dedent(
        """
        def filter_item(data):
            return "\\n".join(data["items"])
        """
    )

    reg = service.register_filter(code)
    result = service.convert_file(reg.filter_id, str(source), str(destination))

    assert destination.read_text(encoding="utf-8") == "red\nblue"
    assert result.filter_id == reg.filter_id
    assert result.source_file_path == str(source.resolve())
    assert result.destination_file_path == str(destination.resolve())
    assert result.file_type == "json"
    assert result.bytes_written == len("red\nblue".encode("utf-8"))
    assert result.overwritten is False


def test_filter_service_converts_txt_file_with_explicit_type(tmp_path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    source = workdir / "input.data"
    destination = workdir / "output.txt"
    source.write_text("one\ntwo\n", encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(workdir)],
    )
    code = textwrap.dedent(
        """
        def filter_item(data):
            return ",".join(data)
        """
    )

    reg = service.register_filter(code)
    result = service.convert_file(
        reg.filter_id,
        str(source),
        str(destination),
        file_type="txt",
    )

    assert destination.read_text(encoding="utf-8") == "one,two"
    assert result.file_type == "txt"


def test_filter_service_convert_file_requires_workdir(tmp_path) -> None:
    source = tmp_path / "data.json"
    destination = tmp_path / "out.txt"
    source.write_text(json.dumps({"x": 1}), encoding="utf-8")
    service = FilterService(filter_ttl_seconds=300, cleanup_interval_seconds=300.0)
    reg = service.register_filter(
        textwrap.dedent(
            """
            def filter_item(data):
                return "ok"
            """
        )
    )

    with pytest.raises(ValueError, match="requires at least one --workdir"):
        service.convert_file(reg.filter_id, str(source), str(destination))


def test_filter_service_convert_file_rejects_source_outside_workdir(tmp_path) -> None:
    workdir = tmp_path / "work"
    outside = tmp_path / "outside"
    workdir.mkdir()
    outside.mkdir()
    source = outside / "data.json"
    destination = workdir / "out.txt"
    source.write_text(json.dumps({"x": 1}), encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(workdir)],
    )
    reg = service.register_filter(
        textwrap.dedent(
            """
            def filter_item(data):
                return "ok"
            """
        )
    )

    with pytest.raises(ValueError, match="outside allowed workdirs"):
        service.convert_file(reg.filter_id, str(source), str(destination))


def test_filter_service_convert_file_rejects_destination_outside_workdir(
    tmp_path,
) -> None:
    workdir = tmp_path / "work"
    outside = tmp_path / "outside"
    workdir.mkdir()
    outside.mkdir()
    source = workdir / "data.json"
    destination = outside / "out.txt"
    source.write_text(json.dumps({"x": 1}), encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(workdir)],
    )
    reg = service.register_filter(
        textwrap.dedent(
            """
            def filter_item(data):
                return "ok"
            """
        )
    )

    with pytest.raises(ValueError, match="Destination path is outside"):
        service.convert_file(reg.filter_id, str(source), str(destination))


def test_filter_service_convert_file_rejects_relative_paths(tmp_path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    source = workdir / "data.json"
    destination = workdir / "out.txt"
    source.write_text(json.dumps({"x": 1}), encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(workdir)],
    )
    reg = service.register_filter(
        textwrap.dedent(
            """
            def filter_item(data):
                return "ok"
            """
        )
    )

    with pytest.raises(ValueError, match="file_path must be an absolute path"):
        service.convert_file(reg.filter_id, "relative.json", str(destination))

    with pytest.raises(ValueError, match="destination_file_path must be an absolute path"):
        service.convert_file(reg.filter_id, str(source), "relative.txt")


def test_filter_service_convert_file_requires_overwrite_for_existing_file(
    tmp_path,
) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    source = workdir / "data.json"
    destination = workdir / "out.txt"
    source.write_text(json.dumps({"x": 1}), encoding="utf-8")
    destination.write_text("old", encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(workdir)],
    )
    reg = service.register_filter(
        textwrap.dedent(
            """
            def filter_item(data):
                return "new"
            """
        )
    )

    with pytest.raises(ValueError, match="already exists"):
        service.convert_file(reg.filter_id, str(source), str(destination))

    result = service.convert_file(
        reg.filter_id,
        str(source),
        str(destination),
        overwrite=True,
    )
    assert destination.read_text(encoding="utf-8") == "new"
    assert result.overwritten is True


def test_filter_service_convert_file_rejects_destination_directory(tmp_path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    source = workdir / "data.json"
    destination = workdir / "existing-dir"
    destination.mkdir()
    source.write_text(json.dumps({"x": 1}), encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(workdir)],
    )
    reg = service.register_filter(
        textwrap.dedent(
            """
            def filter_item(data):
                return "ok"
            """
        )
    )

    with pytest.raises(ValueError, match="Destination path is a directory"):
        service.convert_file(reg.filter_id, str(source), str(destination))


def test_filter_service_convert_file_rejects_same_source_and_destination(
    tmp_path,
) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    source = workdir / "data.json"
    source.write_text(json.dumps({"x": 1}), encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(workdir)],
    )
    reg = service.register_filter(
        textwrap.dedent(
            """
            def filter_item(data):
                return "ok"
            """
        )
    )

    with pytest.raises(ValueError, match="must differ"):
        service.convert_file(reg.filter_id, str(source), str(source), overwrite=True)


def test_filter_service_convert_file_rejects_non_string_result(tmp_path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    source = workdir / "data.json"
    destination = workdir / "out.txt"
    source.write_text(json.dumps({"x": 1}), encoding="utf-8")

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(workdir)],
    )
    reg = service.register_filter(
        textwrap.dedent(
            """
            def filter_item(data):
                return data
            """
        )
    )

    with pytest.raises(ValueError, match="must return a string"):
        service.convert_file(reg.filter_id, str(source), str(destination))
    assert not destination.exists()


def test_filter_service_convert_file_rejects_expired_filters(tmp_path) -> None:
    current_time = {"value": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    workdir = tmp_path / "work"
    workdir.mkdir()
    source = workdir / "items.txt"
    destination = workdir / "out.txt"
    source.write_text("one\ntwo\n", encoding="utf-8")
    service = FilterService(
        filter_ttl_seconds=5,
        cleanup_interval_seconds=30.0,
        now_provider=lambda: current_time["value"],
        workdirs=[str(workdir)],
    )
    reg = service.register_filter(
        textwrap.dedent(
            """
            def filter_item(data):
                return "ok"
            """
        )
    )
    current_time["value"] = current_time["value"] + timedelta(seconds=6)

    with pytest.raises(ValueError, match="expired"):
        service.convert_file(reg.filter_id, str(source), str(destination))


def test_filter_service_convert_file_rechecks_destination_parent_after_mkdir(
    tmp_path,
) -> None:
    workdir = tmp_path / "work"
    outside = tmp_path / "outside"
    workdir.mkdir()
    outside.mkdir()
    source = workdir / "data.json"
    source.write_text(json.dumps({"x": 1}), encoding="utf-8")
    link = workdir / "link"
    link.symlink_to(outside, target_is_directory=True)
    destination = link / "out.txt"

    service = FilterService(
        filter_ttl_seconds=300,
        cleanup_interval_seconds=300.0,
        workdirs=[str(workdir)],
    )
    reg = service.register_filter(
        textwrap.dedent(
            """
            def filter_item(data):
                return "ok"
            """
        )
    )

    with pytest.raises(ValueError, match="Destination path is outside"):
        service.convert_file(reg.filter_id, str(source), str(destination))
