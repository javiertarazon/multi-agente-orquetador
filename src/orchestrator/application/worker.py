from __future__ import annotations

from orchestrator.adapters.executors import executor_for
from orchestrator.adapters.storage import TaskStore
from orchestrator.domain.models import TaskStatus
from orchestrator.domain.models import Notification, TaskResult
import subprocess
import time
from orchestrator.application.security import validate_task


class Worker:
    def __init__(self, store: TaskStore) -> None:
        self.store = store

    def run_once(self) -> int:
        task = self.store.claim_next()
        if not task:
            return 0
        self.store.add_notification(Notification(task_id=task.id, event="task_started",
                                                  message=f"Tarea iniciada por {task.executor.value}"))
        problems = validate_task(task)
        if problems:
            self.store.update_result(task_result(task, TaskStatus.FAILED, "; ".join(problems)))
            return 1
        if any((dependency := self.store.get_result(item)) is None or dependency.status != TaskStatus.SUCCEEDED
               for item in task.depends_on):
            task.status = TaskStatus.QUEUED
            self.store.update_result(task_result(task, TaskStatus.QUEUED, "Dependencias pendientes"))
            return 0
        result = executor_for(task.executor).run(task)
        result = evaluate_result(task, result)
        if result.status == TaskStatus.SUCCEEDED and task.requires_review and task.executor.value != "simulated":
            result.status = TaskStatus.AWAITING_APPROVAL
            result.review_status = "pending"
            result.summary = f"{result.summary}; pendiente de revision de {task.reviewer}"
        if result.status == TaskStatus.FAILED and task.retry_count < task.max_retries:
            task.retry_count += 1
            self.store.requeue(task)
            self.store.add_notification(Notification(task_id=task.id, event="task_retry",
                                                      level="warning", message=f"Evaluacion fallida; reintento {task.retry_count}/{task.max_retries}"))
        else:
            self.store.update_result(result)
            event = "task_completed" if result.status == TaskStatus.SUCCEEDED else "task_failed"
            self.store.add_notification(Notification(task_id=task.id, event=event,
                                                      level="info" if result.status == TaskStatus.SUCCEEDED else "error",
                                                      message=result.summary))
        return 0 if result.status == TaskStatus.SUCCEEDED else 1


def task_result(task, status: TaskStatus, summary: str):
    return TaskResult(task_id=task.id, status=status, summary=summary)


def evaluate_result(task, result: TaskResult) -> TaskResult:
    """Ejecuta los criterios de aceptacion declarados por la tarea."""
    validations = []
    for command in task.validation_commands:
        started = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=task.workspace, text=True,
                                       capture_output=True, timeout=task.timeout_seconds, check=False)
            validations.append({"command": command, "exit_code": completed.returncode,
                                "duration_seconds": round(time.monotonic() - started, 3),
                                "output": (completed.stdout + completed.stderr)[-2000:]})
        except (OSError, subprocess.TimeoutExpired) as error:
            validations.append({"command": command, "exit_code": 124, "output": str(error)})
    result.validations = validations
    failed = [item for item in validations if item["exit_code"] != 0]
    if failed:
        result.status = TaskStatus.FAILED
        result.exit_code = failed[0]["exit_code"]
        result.summary = "La implementacion no cumple las validaciones declaradas"
    return result
