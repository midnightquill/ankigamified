"""Local, per-profile progress with atomic writes; never touches the collection."""

import json
import os
from pathlib import Path
import tempfile


class ProgressStore:
    def __init__(self, path):
        self.path = Path(path)
        self.document = {"version": 1, "profiles": {}, "legacy_migrated": False}
        if self.path.exists():
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict) or not isinstance(loaded.get("profiles"), dict):
                raise ValueError("Invalid progress file; original file has been preserved")
            if loaded.get("version") != 1:
                raise ValueError("Unsupported progress version; original file has been preserved")
            self.document = loaded

    def load_profile(self, name, legacy):
        if name in self.document["profiles"]:
            return self.document["profiles"][name]
        # Old versions combined all profiles. Import that history only once.
        if not self.document.get("legacy_migrated"):
            self.document["legacy_migrated"] = True
            return legacy
        return {}

    def save(self, name, data):
        self.document["profiles"][name] = dict(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix="progress-", suffix=".tmp", delete=False) as f:
                temporary = f.name
                json.dump(self.document, f, ensure_ascii=False, indent=2, allow_nan=False)
                f.write("\n")
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
