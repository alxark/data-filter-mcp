from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..models import LoadedDocument


class DocumentLoader(Protocol):
    file_type: str
    extensions: tuple[str, ...]

    def load(self, file_path: Path) -> LoadedDocument: ...
