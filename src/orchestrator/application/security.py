from __future__ import annotations

import shlex

from orchestrator.domain.models import ApprovalPolicy, Task, TokenBudget

DENIED_COMMANDS = {"format", "del", "rmdir", "Remove-Item", "git reset --hard"}


def validate_task(task: Task) -> list[str]:
    problems: list[str] = []
    if task.timeout_seconds <= 0:
        problems.append("timeout_seconds debe ser positivo")
    if task.max_retries < 0:
        problems.append("max_retries no puede ser negativo")
    if task.approval_policy == ApprovalPolicy.ALWAYS and not task.dry_run:
        problems.append("approval_policy=always requiere aprobacion externa")
    if task.metadata.get("live_trading") is True:
        problems.append("live_trading esta bloqueado: use paper_trading y revision humana")
    budget_data = task.metadata.get("token_budget")
    if budget_data is not None:
        try:
            TokenBudget.model_validate(budget_data)
        except ValueError as error:
            problems.append(f"token_budget invalido: {error}")
    for command in task.validation_commands:
        words = set(shlex.split(" ".join(command), posix=False))
        if words & DENIED_COMMANDS:
            problems.append(f"comando bloqueado: {' '.join(command)}")
    return problems
