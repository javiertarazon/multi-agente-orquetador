from __future__ import annotations

import subprocess
import time

from orchestrator.adapters.executors import executor_for
from orchestrator.adapters.storage import TaskStore
from orchestrator.application.artifact_scanner import ArtifactScanner
from orchestrator.application.auto_reviewer import AutoReviewer
from orchestrator.application.learning_engine import LearningEngine
from orchestrator.application.security import validate_task
from orchestrator.domain.models import (
    Notification,
    TaskAttempt,
    TaskResult,
    TaskStatus,
)


class Worker:
    def __init__(self, store: TaskStore) -> None:
        self.store = store
        self.reviewer = AutoReviewer()
        self.learner = LearningEngine(store)

    def run_once(self) -> int:
        self.store.recover_stale_running()
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
        # retry_count counts retries after the initial execution, so the retry
        # limit is checked only after an attempt has actually run.
        if task.retry_count > task.max_retries and task.max_retries > 0:
            result = task_result(task, TaskStatus.FAILED,
                                 "La tarea alcanzo el maximo de reintentos antes de ejecutarse")
            self.store.update_result(result)
            self.store.add_notification(Notification(task_id=task.id, event="task_failed",
                                                      level="error", message=result.summary))
            return 1
        scanner = ArtifactScanner(task)
        scanner.capture_baseline()
        attempt = self.store.add_attempt(TaskAttempt(task_id=task.id, attempt_number=task.retry_count + 1,
                                                      plan_id=task.plan_id, executor=task.executor,
                                                      model_used=task.model, prompt=task.prompt))
        result = executor_for(task.executor).run(task)
        result = evaluate_result(task, result)
        artifacts = scanner.scan()
        result.changed_files = [artifact.path for artifact in artifacts]
        for artifact in artifacts:
            self.store.add_artifact(artifact)
        result.attempt_id = attempt.id
        self.store.finish_attempt(attempt.id, result, self.learner.classify(result) if result.status != TaskStatus.SUCCEEDED else None)
        decision = self.reviewer.review(task, result, artifacts)
        result.auto_review_score = decision.score
        if result.status == TaskStatus.SUCCEEDED and decision.verdict == "needs_human":
            result.status = TaskStatus.AWAITING_APPROVAL
            result.review_status = "pending"
            result.summary = f"{result.summary}; pendiente de revision de {task.reviewer}"
        elif result.status == TaskStatus.SUCCEEDED and decision.verdict == "rejected":
            result.status = TaskStatus.REJECTED
            result.summary = decision.reason
        if result.status == TaskStatus.FAILED and task.retry_count < task.max_retries:
            task.retry_count += 1
            task.prompt = f"{task.prompt}\n\nContexto de reintento: {self.learner.retry_context(task, result)}"
            self.learner.record_failure(task, result)
            self.store.schedule_retry(task, f"{decision.reason}; intento {task.retry_count}/{task.max_retries}")
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
