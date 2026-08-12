from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutorType(StrEnum):
    SIMULATED = "simulated"
    KILO = "kilo"
    CLINE = "cline"


class ApprovalPolicy(StrEnum):
    NEVER = "never"
    SENSITIVE = "sensitive"
    ALWAYS = "always"


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    prompt: str = Field(min_length=1)
    executor: ExecutorType = ExecutorType.SIMULATED
    status: TaskStatus = TaskStatus.QUEUED
    priority: int = 100
    workspace: str = "."
    allowed_paths: list[str] = Field(default_factory=list)
    validation_commands: list[list[str]] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    max_retries: int = 0
    retry_count: int = 0
    timeout_seconds: int = 900
    approval_policy: ApprovalPolicy = ApprovalPolicy.SENSITIVE
    dry_run: bool = False
    requires_review: bool = True
    review_status: str = "pending"
    reviewer: str = "copilot"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    exit_code: int = 0
    summary: str = ""
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0
    changed_files: list[str] = Field(default_factory=list)
    validations: list[dict[str, Any]] = Field(default_factory=list)
    review_status: str = "pending"
    review_feedback: str = ""
    completed_at: datetime = Field(default_factory=utc_now)


class TaskAttempt(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    task_id: str
    attempt_number: int
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    result: TaskResult | None = None


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    task_id: str
    name: str
    path: str
    content: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class Notification(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    task_id: str | None = None
    event: str
    message: str
    level: str = "info"
    created_at: datetime = Field(default_factory=utc_now)
