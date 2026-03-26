from __future__ import annotations

from pathlib import Path

import yaml

from ..models import LoadedDocument


class YamlLoader:
    file_type = "yaml"
    extensions = (".yaml", ".yml")

    def load(self, file_path: Path) -> LoadedDocument:
        with file_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
