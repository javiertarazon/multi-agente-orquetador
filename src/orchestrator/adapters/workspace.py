from __future__ import annotations

import subprocess
from pathlib import Path


class WorkspaceManager:
    def __init__(self, root: str = ".") -> None:
        self.root = Path(root).resolve()

    def diff_stat(self) -> str:
        result = subprocess.run(["git", "diff", "--stat"], cwd=self.root, text=True, capture_output=True, check=False)
        return result.stdout[-20000:]

    def changed_files(self) -> list[str]:
        result = subprocess.run(["git", "status", "--short"], cwd=self.root, text=True, capture_output=True, check=False)
        return [line[3:] for line in result.stdout.splitlines() if len(line) > 3]
