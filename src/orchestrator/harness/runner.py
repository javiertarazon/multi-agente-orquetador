from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from orchestrator.domain.models import Task, TaskResult, TaskStatus


@dataclass(frozen=True)
class HarnessPolicy:
    """Límites centralizados aplicados antes de ejecutar un worker."""

    max_timeout_seconds: int = 900
    max_output_bytes: int = 20000
    allow_simulated: bool = True


class ExecutionHarness:
    """Envuelve un executor para que nunca deje una tarea sin resultado."""

    def __init__(self, policy: HarnessPolicy | None = None) -> None:
        self.policy = policy or HarnessPolicy()

    def validate(self, task: Task) -> str | None:
        if task.timeout_seconds < 1:
            return "timeout_seconds debe ser positivo"
        if task.timeout_seconds > self.policy.max_timeout_seconds:
            return f"timeout_seconds supera el maximo del harness ({self.policy.max_timeout_seconds})"
        if not self.policy.allow_simulated and task.executor.value == "simulated":
            return "el harness exige un executor real"
        return None

    def run(self, task: Task, operation: Callable[[Task], TaskResult]) -> TaskResult:
        problem = self.validate(task)
        if problem:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED,
                              exit_code=2, summary="Tarea rechazada por el harness",
                              stderr=problem)
        try:
            result = operation(task)
        except Exception as error:  # noqa: BLE001 - frontera de seguridad del worker
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=1,
                              summary="El harness capturo una excepcion del worker",
                              stderr=f"{type(error).__name__}: {error}")
        result.stdout = (result.stdout or "")[-self.policy.max_output_bytes:]
        result.stderr = (result.stderr or "")[-self.policy.max_output_bytes:]
        result.summary = (result.summary or "")[:2000]
        return result
