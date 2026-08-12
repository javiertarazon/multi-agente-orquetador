from pathlib import Path
import json
import sqlite3
import os

from orchestrator.domain.models import Artifact, Notification, Task, TaskResult, TaskStatus


class TaskStore:
    def __init__(self, database: str = "data/orchestrator.db") -> None:
        default_database = "data/orchestrator.db"
        self.database = (os.environ.get("MAOQ_DATABASE", database)
                         if database == default_database else database)
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, priority INTEGER NOT NULL,
                payload TEXT NOT NULL, result TEXT
            )""")
            connection.execute("CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY, task_id TEXT, payload TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS notifications (id TEXT PRIMARY KEY, task_id TEXT, payload TEXT NOT NULL)")

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
        if offset < 0:
            offset = 0
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
        task.status = TaskStatus.QUEUED if approved else TaskStatus.FAILED
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
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT id, payload FROM tasks WHERE status = 'queued' ORDER BY priority, rowid LIMIT 1").fetchone()
            if not row:
                return None
            task = Task.model_validate_json(row["payload"])
            task.status = TaskStatus.RUNNING
            connection.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?", (task.status.value, task.model_dump_json(), task.id))
            return task

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
        with self._connect() as connection:
            connection.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?", (task.status.value, task.model_dump_json(), task.id))

    def add_artifact(self, artifact: Artifact) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO artifacts VALUES (?, ?, ?)", (artifact.id, artifact.task_id, artifact.model_dump_json()))

    def artifacts(self, task_id: str, offset: int = 0, limit: int = 50) -> list[Artifact]:
        if offset < 0:
            offset = 0
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
