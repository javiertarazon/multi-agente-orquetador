from __future__ import annotations

import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from orchestrator.adapters.agent_gateway import AgentGateway, AgentRequest
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
from orchestrator.harness import ExecutionHarness


@dataclass
class _ValidationOutcome:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


def _run_validation_process(
    command: list[str],
    cwd: str,
    timeout: float = 300,
) -> _ValidationOutcome:
    """Ejecuta un comando de validación con timeout robusto (Windows-compatible)."""
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", creationflags=creationflags,
        )
    except FileNotFoundError as error:
        return _ValidationOutcome(exit_code=127, stdout="", stderr=str(error), timed_out=False)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return _ValidationOutcome(
            exit_code=proc.returncode, stdout=stdout or "", stderr=stderr or "", timed_out=False,
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=15)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            stdout, stderr = "", ""
        return _ValidationOutcome(
            exit_code=proc.returncode, stdout=stdout or "", stderr=stderr or "", timed_out=True,
        )


@dataclass
class WorkerStats:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0


class Worker:
    def __init__(self, store: TaskStore) -> None:
        self.store = store
        self.reviewer = AutoReviewer()
        self.learner = LearningEngine(store)
        self.harness = ExecutionHarness()
        self._claim_lock = threading.Lock()

    def run_once(self) -> int:
        self.store.recover_stale_running()
        task = self.store.claim_next()
        if not task:
            return 0
        result = self._execute_claimed(task)
        return 0 if result and result.status == TaskStatus.SUCCEEDED else (1 if result else 0)

    def run_parallel(self, max_workers: int = 2) -> WorkerStats:
        """Ejecuta tareas independientes en paralelo con N workers.

        Cada hilo reclama atomica e independientemente una tarea lista (la
        cola excluye las que tienen dependencias pendientes), la ejecuta y
        guarda su resultado. Los limites del paralelismo se respetan: si el
        plan exige secuencialidad (dependencias), estas se respetan porque
        la tarea dependiente no sale de la cola hasta que su dependencia
        termine con exito.
        """
        self.store.recover_stale_running()
        max_workers = max(1, int(max_workers))
        stats = WorkerStats()
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="maoq-worker") as pool:
            futures = [pool.submit(self._worker_loop, stats) for _ in range(max_workers)]
            for future in futures:
                future.result()
        return stats

    def _worker_loop(self, stats: WorkerStats) -> None:
        """Bucle de un worker: ejecuta tareas listas hasta agotar la cola."""
        while True:
            task = self.store.claim_next()
            if not task:
                return
            result = self.harness.run(task, self._execute_claimed)
            if result.status == TaskStatus.FAILED and not self.store.get_result(task.id):
                try:
                    self.store.update_result(result)
                except (KeyError, OSError):
                    return
            if result:
                stats.processed += 1
                if result.status == TaskStatus.SUCCEEDED:
                    stats.succeeded += 1
                elif result.status in (TaskStatus.FAILED, TaskStatus.REJECTED, TaskStatus.TIMED_OUT):
                    stats.failed += 1

    def _execute_claimed(self, task) -> TaskResult | None:
        self.store.add_notification(Notification(task_id=task.id, event="task_started",
                                                  message=f"Tarea iniciada por {task.executor.value}"))
        problems = validate_task(task)
        if problems:
            result = task_result(task, TaskStatus.FAILED, "; ".join(problems))
            self.store.update_result(result)
            return result
        if any((dependency := self.store.get_result(item)) is None or dependency.status != TaskStatus.SUCCEEDED
               for item in task.depends_on):
            task.status = TaskStatus.QUEUED
            result = task_result(task, TaskStatus.QUEUED, "Dependencias pendientes")
            self.store.update_result(result)
            return result
        # retry_count counts retries after the initial execution, so the retry
        # limit is checked only after an attempt has actually run.
        if task.retry_count > task.max_retries and task.max_retries > 0:
            result = task_result(task, TaskStatus.FAILED,
                                 "La tarea alcanzo el maximo de reintentos antes de ejecutarse")
            self.store.update_result(result)
            self.store.add_notification(Notification(task_id=task.id, event="task_failed",
                                                      level="error", message=result.summary))
            return result
        scanner = ArtifactScanner(task)
        scanner.capture_baseline()
        attempt = self.store.add_attempt(TaskAttempt(task_id=task.id, attempt_number=task.retry_count + 1,
                                                      plan_id=task.plan_id, executor=task.executor,
                                                      model_used=task.model, prompt=task.prompt))
        if any(tag.lower() in {"enjambre", "swarm", "modo_dios"} for tag in task.tags):
            result, selected_agent = AgentGateway().swarm_round(AgentRequest(task))
            if result.summary:
                result.summary = f"{result.summary} [agente seleccionado: {selected_agent}]"
        else:
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
        return result


def task_result(task, status: TaskStatus, summary: str):
    return TaskResult(task_id=task.id, status=status, summary=summary)


def evaluate_result(task, result: TaskResult) -> TaskResult:
    """Ejecuta los criterios de aceptacion declarados por la tarea."""
    validations = []
    validation_timeout = min(300, task.timeout_seconds)
    for command in task.validation_commands:
        started = time.monotonic()
        outcome = _run_validation_process(command, task.workspace, timeout=validation_timeout)
        validations.append({
            "command": command,
            "exit_code": outcome.exit_code,
            "duration_seconds": round(time.monotonic() - started, 3),
            "output": (outcome.stdout + outcome.stderr)[-2000:],
        })
    result.validations = validations
    failed = [item for item in validations if item["exit_code"] != 0]
    if failed:
        result.status = TaskStatus.FAILED
        result.exit_code = failed[0]["exit_code"]
        result.summary = "La implementacion no cumple las validaciones declaradas"
    return result
