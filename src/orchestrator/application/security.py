from __future__ import annotations

import shlex

from orchestrator.domain.models import ApprovalPolicy, Task

DENIED_COMMANDS = {"format", "del", "rmdir", "Remove-Item", "git reset --hard"}


def validate_task(task: Task) -> list[str]:
    problems: list[str] = []
    if task.timeout_seconds <= 0:
        problems.append("timeout_seconds debe ser positivo")
    if task.max_retries < 0:
        problems.append("max_retries no puede ser negativo")
    if task.approval_policy == ApprovalPolicy.ALWAYS and not task.dry_run:
        problems.append("approval_policy=always requiere aprobacion externa")
    for command in task.validation_commands:
        words = set(shlex.split(" ".join(command), posix=False))
        if words & DENIED_COMMANDS:
            problems.append(f"comando bloqueado: {' '.join(command)}")
    return problems
