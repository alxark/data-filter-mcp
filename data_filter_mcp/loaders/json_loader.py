from __future__ import annotations

import json
from pathlib import Path

from ..models import LoadedDocument


class JsonLoader:
    file_type = "json"
    extensions = (".json",)

    def load(self, file_path: Path) -> LoadedDocument:
        with file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
