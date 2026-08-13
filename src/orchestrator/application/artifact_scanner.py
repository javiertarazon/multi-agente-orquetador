from __future__ import annotations

import hashlib
import os
from pathlib import Path

from orchestrator.domain.models import Artifact, Task


class ArtifactScanner:
    """Detecta cambios dentro de las rutas permitidas de una tarea."""

    def __init__(self, task: Task) -> None:
        self.task = task
        self.workspace = Path(task.workspace).resolve()
        self._baseline: dict[Path, str] = {}

    def capture_baseline(self) -> None:
        self._baseline = {path: self._hash(path) for path in self._files()}

    def scan(self) -> list[Artifact]:
        current = {path: self._hash(path) for path in self._files()}
        artifacts: list[Artifact] = []
        for path, digest in current.items():
            previous = self._baseline.get(path)
            if previous == digest:
                continue
            artifacts.append(Artifact(task_id=self.task.id, name=path.name, path=str(path),
                                      hash_sha256=digest, size_bytes=path.stat().st_size,
                                      previous_hash=previous,
                                      modification_type="created" if previous is None else "modified",
                                      is_within_allowed_paths=self._allowed(path)))
        for path, digest in self._baseline.items():
            if path not in current:
                artifacts.append(Artifact(task_id=self.task.id, name=path.name, path=str(path),
                                          previous_hash=digest, modification_type="deleted",
                                          is_within_allowed_paths=self._allowed(path)))
        return artifacts

    def _files(self) -> list[Path]:
        if not self.workspace.exists():
            return []
        result: list[Path] = []
        for root, directories, files in os.walk(self.workspace):
            directories[:] = [name for name in directories if name not in {".git", ".venv", "__pycache__"}]
            for name in files:
                path = Path(root, name)
                result.append(path)
        return result

    def _allowed(self, path: Path) -> bool:
        if not self.task.allowed_paths:
            return True
        resolved = path.resolve()
        for raw_path in self.task.allowed_paths:
            pattern = Path(raw_path)
            if "*" in raw_path:
                try:
                    if resolved.match(str(pattern).replace("\\", "/")):
                        return True
                except ValueError:
                    continue
            else:
                allowed = pattern.resolve()
                if resolved == allowed or allowed in resolved.parents:
                    return True
        return False

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()
