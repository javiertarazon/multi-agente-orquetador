#!/usr/bin/env python3
import sys
import os
import json
import sqlite3
import threading
import time
from datetime import datetime, UTC
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from enum import Enum
from typing import Optional, List, Dict, Any

# ===== Minimal reimplementation to avoid cache issues =====

class TaskStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    RETRY_WAIT = "retry_wait"
    AWAITING_APPROVAL = "awaiting_approval"

class ExecutorType(Enum):
    SIMULATED = "simulated"
    KILO = "kilo"
    CLINE = "cline"
    HERMES = "hermes"

@dataclass
class Task:
    id: str
    prompt: str
    executor: str  # Will convert to enum later
    priority: int
    workspace: str
    allowed_paths: list
    validation_commands: list
    depends_on: list
    max_retries: int
    retry_count: int
    timeout_seconds: int
    dry_run: bool
    approval_policy: str
    requires_review: bool
    reviewer: str
    plan_id: str
    model: Optional[str] = None
    backoff_base: float = 2.0
    scheduled_at: Optional[str] = None
    goal_id: Optional[str] = None
    tags: list = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    status: str = "queued"  # String to avoid enum issues
    
    # Add any extra fields that might be in the DB
    review_status: Optional[str] = None
    
    def __post_init__(self):
        # Handle executor string
        if isinstance(self.executor, str):
            pass  # Keep as string
        # Handle status string
        if isinstance(self.status, str):
            pass

@dataclass
class TaskResult:
    task_id: str
    status: str
    summary: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    validations: list = None
    changed_files: list = None
    attempt_id: str = None
    auto_review_score: float = 0.0
    review_status: str = None

class SimulatedExecutor:
    def run(self, task):
        return TaskResult(
            task_id=task.id,
            status="succeeded",
            summary=f"Tarea simulada completada: {task.prompt}"
        )

def run_validation_process(command, cwd, timeout=300):
    import subprocess
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", creationflags=creationflags,
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        return {
            "exit_code": proc.returncode,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=15)
        except:
            stdout, stderr = "", ""
        return {
            "exit_code": 124,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "timed_out": True,
        }
    except FileNotFoundError as e:
        return {
            "exit_code": 127,
            "stdout": "",
            "stderr": str(e),
            "timed_out": False,
        }

def evaluate_result(task, result):
    validations = []
    validation_timeout = min(300, task.timeout_seconds)
    for command in task.validation_commands:
        outcome = run_validation_process(command, task.workspace, timeout=validation_timeout)
        validations.append({
            "command": command,
            "exit_code": outcome["exit_code"],
            "duration_seconds": 0,
            "output": (outcome["stdout"] + outcome["stderr"])[-2000:],
        })
    result.validations = validations
    failed = [v for v in validations if v["exit_code"] != 0]
    if failed:
        result.status = "failed"
        result.summary = f"La implementacion no cumple las validaciones declaradas. Fallaron {len(failed)} validaciones."
    return result

class TaskStore:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def list(self, limit=1000):
        conn = self._connect()
        rows = conn.execute("SELECT id, payload FROM tasks ORDER BY priority, rowid LIMIT ?", (limit,)).fetchall()
        conn.close()
        tasks = []
        for row in rows:
            data = json.loads(row["payload"])
            tasks.append(Task(**data))
        return tasks
    
    def get(self, task_id):
        conn = self._connect()
        row = conn.execute("SELECT payload FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
        if row:
            data = json.loads(row["payload"])
            return Task(**data)
        return None
    
    def claim_next(self):
        conn = self._connect()
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT id, payload FROM tasks WHERE status = 'queued' ORDER BY priority, rowid"
        ).fetchall()
        for row in rows:
            data = json.loads(row["payload"])
            task = Task(**data)
            if not task.depends_on:
                task.status = "running"
                task.updated_at = datetime.now(UTC).isoformat()
                conn.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?",
                            (task.status, json.dumps(task.__dict__, default=str), task.id))
                conn.commit()
                conn.close()
                return task
            dependencies = [conn.execute("SELECT status FROM tasks WHERE id = ?", (item,)).fetchone()
                            for item in task.depends_on]
            if all(dep and dep["status"] == "succeeded" for dep in dependencies):
                task.status = "running"
                task.updated_at = datetime.now(UTC).isoformat()
                conn.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?",
                            (task.status, json.dumps(task.__dict__, default=str), task.id))
                conn.commit()
                conn.close()
                return task
        conn.close()
        return None
    
    def requeue(self, task):
        task.status = "queued"
        task.updated_at = datetime.now(UTC).isoformat()
        conn = self._connect()
        conn.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?",
                    (task.status, json.dumps(task.__dict__, default=str), task.id))
        conn.commit()
        conn.close()
    
    def get_result(self, task_id):
        conn = self._connect()
        row = conn.execute("SELECT result FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
        if row and row["result"]:
            return json.loads(row["result"])
        return None
    
    def update_result(self, result):
        conn = self._connect()
        conn.execute("UPDATE tasks SET result = ? WHERE id = ?",
                    (json.dumps(result.__dict__, default=str), result.task_id))
        conn.commit()
        conn.close()

class Worker:
    def __init__(self, store):
        self.store = store
        self.executor = SimulatedExecutor()
    
    def run_parallel(self, max_workers=2):
        max_workers = max(1, int(max_workers))
        stats = {"processed": 0, "succeeded": 0, "failed": 0}
        
        def worker_loop(stats):
            while True:
                task = self.store.claim_next()
                if not task:
                    return
                print(f"Worker claimed: {task.id[:8]}")
                result = self._execute_claimed(task)
                if result:
                    stats["processed"] += 1
                    if result.status == "succeeded":
                        stats["succeeded"] += 1
                    elif result.status in ("failed", "rejected"):
                        stats["failed"] += 1
        
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(worker_loop, stats) for _ in range(max_workers)]
            for f in futures:
                f.result()
        return stats
    
    def _execute_claimed(self, task):
        print(f"Executing task: {task.id[:8]}")
        result = self.executor.run(task)
        print(f"Executor result: {result.status}")
        result = evaluate_result(task, result)
        print(f"After validation: {result.status}")
        # Update task status based on result
        if result.status == "succeeded":
            task.status = "succeeded"
        else:
            task.status = "failed"
        task.updated_at = datetime.now(UTC).isoformat()
        self.store.update_result(result)
        # Also update the task status in DB
        conn = self.store._connect()
        conn.execute("UPDATE tasks SET status = ?, payload = ? WHERE id = ?",
                    (task.status, json.dumps(task.__dict__, default=str), task.id))
        conn.commit()
        conn.close()
        return result

class SimulatedExecutor:
    def run(self, task):
        return TaskResult(
            task_id=task.id,
            status="succeeded",
            summary=f"Tarea simulada completada: {task.prompt}"
        )

def run_validation_process(command, cwd, timeout=300):
    import subprocess
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", creationflags=creationflags,
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        return {
            "exit_code": proc.returncode,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=15)
        except:
            stdout, stderr = "", ""
        return {
            "exit_code": 124,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "timed_out": True,
        }
    except FileNotFoundError as e:
        return {
            "exit_code": 127,
            "stdout": "",
            "stderr": str(e),
            "timed_out": False,
        }

def evaluate_result(task, result):
    import subprocess
    validations = []
    validation_timeout = min(300, task.timeout_seconds)
    for command in task.validation_commands:
        outcome = run_validation_process(command, task.workspace, timeout=validation_timeout)
        validations.append({
            "command": command,
            "exit_code": outcome["exit_code"],
            "duration_seconds": 0,
            "output": (outcome["stdout"] + outcome["stderr"])[-2000:],
        })
    result.validations = validations
    failed = [v for v in validations if v["exit_code"] != 0]
    if failed:
        result.status = "failed"
        result.summary = f"La implementacion no cumple las validaciones declaradas. Fallaron {len(failed)} validaciones."
    return result

def main():
    plan_store = TaskStore('data/plans/4d0425c8644346398aed52a8379edefc.db')
    worker = Worker(plan_store)
    stats = worker.run_parallel(max_workers=2)
    print(f"Stats: processed={stats['processed']}, succeeded={stats['succeeded']}, failed={stats['failed']}")

if __name__ == "__main__":
    main()