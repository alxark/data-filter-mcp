from __future__ import annotations

from pathlib import Path

from ..models import LoadedDocument


class TxtLoader:
    file_type = "txt"
    extensions = (".txt",)

    def load(self, file_path: Path) -> LoadedDocument:
        return file_path.read_text(encoding="utf-8").splitlines()
