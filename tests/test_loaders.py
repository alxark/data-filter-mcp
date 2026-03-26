from __future__ import annotations

import json

import pytest

from data_filter_mcp.loaders.factory import load_document, resolve_file_type


def test_load_document_detects_json_by_extension(tmp_path) -> None:
    file_path = tmp_path / "data.json"
    file_path.write_text(json.dumps({"items": [1, 2, 3]}), encoding="utf-8")

    document, file_type = load_document(file_path)

    assert file_type == "json"
    assert document == {"items": [1, 2, 3]}


def test_load_document_supports_explicit_yaml_type(tmp_path) -> None:
    file_path = tmp_path / "data.custom"
    file_path.write_text("name: alice\nitems:\n  - one\n  - two\n", encoding="utf-8")

    document, file_type = load_document(file_path, "yaml")

    assert file_type == "yaml"
    assert document == {"name": "alice", "items": ["one", "two"]}


def test_load_document_reads_text_as_lines(tmp_path) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text("alpha\nbeta\n", encoding="utf-8")

    document, file_type = load_document(file_path)

    assert file_type == "txt"
    assert document == ["alpha", "beta"]


def test_resolve_file_type_rejects_unknown_extensions(tmp_path) -> None:
    file_path = tmp_path / "data.bin"
    file_path.write_text("payload", encoding="utf-8")

    with pytest.raises(ValueError, match="Could not detect file type"):
        resolve_file_type(file_path)
