from __future__ import annotations

from pathlib import Path

from ..models import LoadedDocument
from .base import DocumentLoader
from .json_loader import JsonLoader
from .txt_loader import TxtLoader
from .yaml_loader import YamlLoader

LOADERS: dict[str, DocumentLoader] = {
    "json": JsonLoader(),
    "txt": TxtLoader(),
    "yaml": YamlLoader(),
}

EXTENSION_TO_FILE_TYPE = {
    ".json": "json",
    ".txt": "txt",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def normalize_file_type(file_type: str) -> str:
    normalized = file_type.strip().lower()
    if normalized not in LOADERS:
        raise ValueError(f"Unsupported file type: {file_type}")
    return normalized


def resolve_file_type(file_path: Path, file_type: str | None = None) -> str:
    if file_type is not None:
        return normalize_file_type(file_type)

    suffix = file_path.suffix.lower()
    resolved = EXTENSION_TO_FILE_TYPE.get(suffix)
    if resolved is None:
        raise ValueError(f"Could not detect file type from extension: {file_path.name}")
    return resolved


def load_document(
    file_path: Path,
    file_type: str | None = None,
) -> tuple[LoadedDocument, str]:
    resolved_file_type = resolve_file_type(file_path, file_type)
    loader = LOADERS[resolved_file_type]
    return loader.load(file_path), resolved_file_type
