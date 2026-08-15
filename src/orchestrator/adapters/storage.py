import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from orchestrator.domain.models import (
    Artifact,
    Episode,
    Goal,
    Notification,
    Task,
    TaskAttempt,
    TaskResult,
    TaskStatus,
)


class TaskStore:
    def __init__(self, database: str = "data/orchestrator.db") -> None:
        default_database = "data/orchestrator.db"
        self.database = (os.environ.get("MAOQ_DATABASE", database)
                         if database == default_database else database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, priority INTEGER NOT NULL,
                payload TEXT NOT NULL, result TEXT
            )""")
            connection.execute("CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY, task_id TEXT, payload TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS notifications (id TEXT PRIMARY KEY, task_id TEXT, payload TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS task_attempts (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, payload TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS episodes (id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, payload TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS goals (id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, payload TEXT NOT NULL)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_attempts_task ON task_attempts(task_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_episodes_plan ON episodes(plan_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_goals_plan ON goals(plan_id)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def add(self, task: Task) -> Task:
        with self._connect() as connection:
            connection.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, NULL)",
                (task.id, task.status.value, task.priority, task.model_dump_json()))
        return task

    def list(self, status: TaskStatus | None = None, offset: int = 0, limit: int = 50) -> list[Task]:
        offset = max(offset, 0)
        if limit <= 0:
            limit = 50
        elif limit > 1000:
            limit = 1000
            
        query = "SELECT payload FROM tasks"
        parameters: tuple[str, ...] = ()
        if status:
            query += " WHERE status = ?"
            parameters = (status.value,)
        query += " ORDER BY priority ASC, rowid ASC LIMIT ?, ?"
        parameters = parameters + (offset, limit)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [Task.model_validate_json(row["payload"]) for row in rows]

    def list_with_summary(self, status: TaskStatus | None = None, offset: int = 0, limit: int = 50, compact: bool = False) -> list[dict]:
        """List tasks with pagination and optional compact summary response."""
        tasks = self.list(status=status, offset=offset, limit=limit)
        if compact:
            return [{"id": task.id, "status": task.status.value, "executor": task.executor.value} for task in tasks]
        return [{"id": task.id, "status": task.status.value, "executor": task.executor.value,
                 "prompt": task.prompt[:200] + ("..." if len(task.prompt) > 200 else "")} for task in tasks]
    
    def list_to_dict(self, status: TaskStatus | None = None, offset: int = 0, limit: int = 50, compact: bool = False) -> list[dict]:
        """Convenience method for MCP server to return tasks as dictionaries."""
        return self.list_with_summary(status=status, offset=offset, limit=limit, compact=compact)

    def get(self, task_id: str) -> Task | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return Task.model_validate_json(row["payload"]) if row else None

    def update_result(self, result: TaskResult) -> None:
        task = self.get(result.task_id)
        if not task:
            raise KeyError(result.task_id)
        task.status = result.status
        task.updated_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute("UPDATE tasks SET status = ?, payload = ?, result = ? WHERE id = ?",
                (result.status.value, task.model_dump_json(), json.dumps(result.model_dump(mode="json")), task.id))

    def review(self, task_id: str, approved: bool, reviewer: str = "copilot",
               feedback: str = "") -> Task:
        task = self.get(task_id)
        if not task:
            raise KeyError(task_id)
        if task.status != TaskStatus.AWAITING_APPROVAL:
            raise ValueError("La tarea no esta esperando aprobacion")
        task.review_status = "approved" if approved else "rejected"
        task.reviewer = reviewer
        task.status = TaskStatus.SUCCEEDED if approved else TaskStatus.REJECTED
        result = self.get_result(task_id)
        if result:
            result.review_status = task.review_status
            result.review_feedback = feedback
        with self._connect() as connection:
            connection.execute("UPDATE tasks SET status = ?, payload = ?, result = ? WHERE id = ?",
                (task.status.value, task.model_dump_json(),
                 json.dumps(result.model_dump(mode="json")) if result else None, task.id))
        return task

    def claim_next(self) -> Task | None:
        self.promote_due_retries()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT id, payload FROM tasks WHERE status = 'queued' ORDER BY priority, rowid LIMIT 1").fetchone()
            if not row:
                return None
            task = Task.model_validate_json(row["payload"])
            task.status = TaskStatus.RUNNING
            task.updated_at = datetime.now(UTC)
            connection.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?", (task.status.value, task.model_dump_json(), task.id))
            return task

    def promote_due_retries(self) -> list[str]:
        """Mueve reintentos cuyo backoff ya vencio a la cola ejecutable."""
        now = datetime.now(UTC)
        promoted: list[str] = []
        for task in self.list(status=TaskStatus.RETRY_WAIT, limit=1000):
            if task.scheduled_at and task.scheduled_at > now:
                continue
            task.status = TaskStatus.QUEUED
            task.scheduled_at = None
            task.updated_at = now
            with self._connect() as connection:
                connection.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?",
                                   (task.status.value, task.model_dump_json(), task.id))
            promoted.append(task.id)
        return promoted

    def recover_stale_running(self, max_age_seconds: int = 300) -> list[str]:
        """Reencola tareas cuyo worker desaparecio sin guardar resultado."""
        cutoff = datetime.now(UTC) - timedelta(seconds=max(1, max_age_seconds))
        recovered: list[str] = []
        for task in self.list(status=TaskStatus.RUNNING, limit=1000):
            updated = task.updated_at
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=UTC)
            if updated >= cutoff:
                continue
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                self.schedule_retry(task, "Worker sin heartbeat")
            else:
                task.status = TaskStatus.TIMED_OUT
                task.updated_at = datetime.now(UTC)
                with self._connect() as connection:
                    connection.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?",
                                       (task.status.value, task.model_dump_json(), task.id))
            self.add_notification(Notification(task_id=task.id, event="task_recovered",
                                                level="warning", message="Tarea running recuperada por timeout del worker"))
            recovered.append(task.id)
        return recovered

    def cancel(self, task_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM tasks WHERE id = ? AND status IN ('queued','running')", (task_id,)).fetchone()
            if not row:
                return False
            task = Task.model_validate_json(row["payload"])
            task.status = TaskStatus.CANCELLED
            result = connection.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?", (TaskStatus.CANCELLED.value, task.model_dump_json(), task_id))
            return result.rowcount > 0

    def requeue(self, task: Task) -> None:
        task.status = TaskStatus.QUEUED
        task.updated_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?", (task.status.value, task.model_dump_json(), task.id))

    def schedule_retry(self, task: Task, reason: str = "") -> None:
        delay = task.backoff_base ** max(1, task.retry_count)
        task.status = TaskStatus.RETRY_WAIT
        task.scheduled_at = datetime.now(UTC) + timedelta(seconds=delay)
        task.updated_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?",
                               (task.status.value, task.model_dump_json(), task.id))
        self.add_notification(Notification(task_id=task.id, event="task_retry_scheduled", level="warning",
                                           message=f"Reintento en {delay:.1f}s: {reason}"))

    def add_attempt(self, attempt: TaskAttempt) -> TaskAttempt:
        with self._connect() as connection:
            connection.execute("INSERT INTO task_attempts VALUES (?, ?, ?)",
                               (attempt.id, attempt.task_id, attempt.model_dump_json()))
        return attempt

    def finish_attempt(self, attempt_id: str, result: TaskResult, error_category: str | None = None) -> None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM task_attempts WHERE id = ?", (attempt_id,)).fetchone()
            if not row:
                raise KeyError(attempt_id)
            attempt = TaskAttempt.model_validate_json(row["payload"])
            attempt.completed_at = datetime.now(UTC)
            attempt.heartbeat_at = attempt.completed_at
            attempt.result = result
            attempt.error_category = error_category
            connection.execute("UPDATE task_attempts SET payload = ? WHERE id = ?", (attempt.model_dump_json(), attempt_id))

    def touch_attempt(self, attempt_id: str) -> None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM task_attempts WHERE id = ?", (attempt_id,)).fetchone()
            if not row:
                return
            attempt = TaskAttempt.model_validate_json(row["payload"])
            attempt.heartbeat_at = datetime.now(UTC)
            connection.execute("UPDATE task_attempts SET payload = ? WHERE id = ?", (attempt.model_dump_json(), attempt_id))

    def attempts(self, task_id: str) -> list[TaskAttempt]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM task_attempts WHERE task_id = ? ORDER BY rowid", (task_id,)).fetchall()
        return [TaskAttempt.model_validate_json(row["payload"]) for row in rows]

    def add_episode(self, episode: Episode) -> Episode:
        with self._connect() as connection:
            connection.execute("INSERT INTO episodes VALUES (?, ?, ?)",
                               (episode.id, episode.plan_id, episode.model_dump_json()))
        return episode

    def similar_episodes(self, plan_id: str, error_category: str, limit: int = 5) -> list[Episode]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM episodes WHERE plan_id = ? ORDER BY rowid DESC LIMIT ?",
                                      (plan_id, max(1, min(limit, 100)))).fetchall()
        return [episode for row in rows if (episode := Episode.model_validate_json(row["payload"])).error_category == error_category]

    def add_goal(self, goal: Goal) -> Goal:
        with self._connect() as connection:
            connection.execute("INSERT INTO goals VALUES (?, ?, ?)", (goal.id, goal.plan_id, goal.model_dump_json()))
        return goal

    def goals(self, plan_id: str) -> list[Goal]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM goals WHERE plan_id = ? ORDER BY rowid", (plan_id,)).fetchall()
        return [Goal.model_validate_json(row["payload"]) for row in rows]

    def get_goal(self, goal_id: str) -> Goal | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return Goal.model_validate_json(row["payload"]) if row else None

    def update_goal(self, goal: Goal) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE goals SET payload = ? WHERE id = ?", (goal.model_dump_json(), goal.id))

    def add_artifact(self, artifact: Artifact) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO artifacts VALUES (?, ?, ?)", (artifact.id, artifact.task_id, artifact.model_dump_json()))

    def artifacts(self, task_id: str, offset: int = 0, limit: int = 50) -> list[Artifact]:
        offset = max(offset, 0)
        if limit <= 0:
            limit = 50
        elif limit > 1000:
            limit = 1000
            
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM artifacts WHERE task_id = ? ORDER BY rowid ASC LIMIT ?, ?", (task_id, offset, limit)).fetchall()
        return [Artifact.model_validate_json(row["payload"]) for row in rows]

    def artifacts_with_summary(self, task_id: str, offset: int = 0, limit: int = 50, compact: bool = False) -> list[dict]:
        """Convenience method for MCP server to return artifacts as dictionaries with pagination and optional compact summary."""
        artifacts = self.artifacts(task_id, offset=offset, limit=limit)
        if compact:
            return [{"id": artifact.id, "name": artifact.name, "path": artifact.path} for artifact in artifacts]
        return [artifact.model_dump(mode="json") for artifact in artifacts]

    def get_result(self, task_id: str) -> TaskResult | None:
        with self._connect() as connection:
            row = connection.execute("SELECT result FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return TaskResult.model_validate_json(row["result"]) if row and row["result"] else None

    def add_notification(self, notification: Notification) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO notifications VALUES (?, ?, ?)",
                               (notification.id, notification.task_id, notification.model_dump_json()))

    def notifications(self, task_id: str | None = None, limit: int = 50) -> list[Notification]:
        query = "SELECT payload FROM notifications"
        parameters: tuple = ()
        if task_id:
            query += " WHERE task_id = ?"
            parameters = (task_id,)
        query += " ORDER BY rowid DESC LIMIT ?"
        parameters += (max(1, min(limit, 200)),)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [Notification.model_validate_json(row["payload"]) for row in rows]
