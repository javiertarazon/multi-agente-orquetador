from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    RETRY_WAIT = "retry_wait"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ExecutorType(StrEnum):
    SIMULATED = "simulated"
    KILO = "kilo"
    CLINE = "cline"


class PlanContract(BaseModel):
    """Contrato versionado emitido por el agente principal."""

    schema_version: str = "1.0"
    plan_id: str = Field(default_factory=lambda: uuid4().hex)
    objective: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(default_factory=list)
    workspace: str = "."
    executor_order: list[ExecutorType] = Field(
        default_factory=lambda: [ExecutorType.KILO, ExecutorType.CLINE, ExecutorType.SIMULATED]
    )
    max_iterations: int = Field(default=3, ge=1, le=100)
    max_total_seconds: int = Field(default=3600, ge=1)
    dry_run: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenBudget(BaseModel):
    """Límites explícitos para impedir que un loop consuma recursos sin fin."""

    schema_version: str = "1.0"
    max_prompt_tokens: int = Field(default=4000, ge=1)
    max_output_tokens: int = Field(default=8000, ge=1)
    max_attempts: int = Field(default=3, ge=1)
    max_repair_attempts: int = Field(default=2, ge=0)


class EvaluationReport(BaseModel):
    """Evidencia compacta y serializable de una decisión del supervisor."""

    schema_version: str = "1.0"
    task_id: str
    attempt_id: str | None = None
    verdict: str = "uncertain"
    passed_checks: int = 0
    failed_checks: int = 0
    evidence: list[str] = Field(default_factory=list)
    failure_reason: str = ""
    next_action: str = "escalate"


class AgentCapabilities(BaseModel):
    provider: str
    version: str = "unknown"
    supports_plan: bool = False
    supports_execute: bool = True
    supports_review: bool = False
    supports_streaming: bool = False
    free_model: bool = True


class ApprovalPolicy(StrEnum):
    NEVER = "never"
    SENSITIVE = "sensitive"
    ALWAYS = "always"
    AUTO_ON_PASS = "auto_on_pass"
    MANUAL = "manual"
    MILESTONE = "milestone"


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
    plan_id: str | None = None
    model: str | None = None
    backoff_base: float = 2.0
    scheduled_at: datetime | None = None
    goal_id: str | None = None
    tags: list[str] = Field(default_factory=list)
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
    attempt_id: str | None = None
    auto_review_score: float | None = None
    financial_metrics: dict[str, Any] | None = None
    completed_at: datetime = Field(default_factory=utc_now)


class TaskAttempt(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    task_id: str
    attempt_number: int
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    result: TaskResult | None = None
    plan_id: str | None = None
    executor: ExecutorType | None = None
    model_used: str | None = None
    prompt: str = ""
    heartbeat_at: datetime | None = None
    error_category: str | None = None
    retry_reason: str = ""


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    task_id: str
    name: str
    path: str
    content: str = ""
    hash_sha256: str = ""
    size_bytes: int = 0
    modification_type: str = "created"
    previous_hash: str | None = None
    is_within_allowed_paths: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class Notification(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    task_id: str | None = None
    event: str
    message: str
    level: str = "info"
    created_at: datetime = Field(default_factory=utc_now)


class Episode(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    plan_id: str
    task_id: str
    error_category: str
    error_message: str
    fix_applied: str = ""
    success: bool = False
    executor: ExecutorType | None = None
    model_used: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Goal(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    plan_id: str
    parent_id: str | None = None
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.QUEUED
    progress: float = 0.0
    success_criteria: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
