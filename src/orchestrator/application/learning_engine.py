from __future__ import annotations

import re

from orchestrator.adapters.storage import TaskStore
from orchestrator.domain.models import Episode, Task, TaskResult


class LearningEngine:
    """Convierte fallos repetibles en contexto breve para el siguiente intento."""

    _patterns = {
        "timeout": (r"timeout", r"timed out", r"deadline", r"\b124\b"),
        "syntax_error": (r"syntaxerror", r"parseerror", r"invalid syntax"),
        "dependency_failure": (r"modulenotfounderror", r"importerror", r"no module named"),
        "validation_failure": (r"assertionerror", r"test failed", r"validation"),
        "security_violation": (r"permission denied", r"access denied", r"blocked"),
    }

    def __init__(self, store: TaskStore) -> None:
        self.store = store

    def classify(self, result: TaskResult) -> str:
        if result.exit_code == 124:
            return "timeout"
        text = f"{result.stdout}\n{result.stderr}".lower()
        for category, patterns in self._patterns.items():
            if any(re.search(pattern, text) for pattern in patterns):
                return category
        return "unknown"

    def record_failure(self, task: Task, result: TaskResult) -> Episode:
        category = self.classify(result)
        plan_id = task.plan_id or str(task.metadata.get("plan_id", "global"))
        episode = Episode(plan_id=plan_id, task_id=task.id, error_category=category,
                          error_message=(result.stderr or result.summary)[:1000],
                          executor=task.executor, model_used=task.model)
        return self.store.add_episode(episode)

    def retry_context(self, task: Task, result: TaskResult) -> str:
        category = self.classify(result)
        plan_id = task.plan_id or str(task.metadata.get("plan_id", "global"))
        similar = self.store.similar_episodes(plan_id, category)
        if category == "timeout":
            return "Intento previo agotó tiempo: trabaja solo en el archivo indicado y no explores el repositorio completo."
        if similar:
            return f"Evita repetir el fallo previo clasificado como {category}. Comprueba primero la causa indicada por las validaciones."
        return f"Corrige el fallo previo ({category}) y ejecuta solo las validaciones declaradas."
