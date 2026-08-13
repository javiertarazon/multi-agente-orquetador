from __future__ import annotations

from dataclasses import dataclass

from orchestrator.domain.models import ApprovalPolicy, Artifact, ExecutorType, Task, TaskResult


@dataclass(frozen=True)
class ReviewDecision:
    verdict: str
    score: float
    reason: str


class AutoReviewer:
    """Aplica criterios reproducibles antes de solicitar una revisión humana."""

    def review(self, task: Task, result: TaskResult, artifacts: list[Artifact]) -> ReviewDecision:
        validations_passed = all(item.get("exit_code") == 0 for item in result.validations)
        safe_artifacts = all(item.is_within_allowed_paths for item in artifacts)
        successful = result.exit_code == 0 and validations_passed and safe_artifacts
        score = 1.0 if successful else 0.0
        if task.metadata.get("target_return") is not None:
            metrics = result.financial_metrics or {}
            if not self._metrics_pass(task, metrics):
                return ReviewDecision("rejected", 0.0, "Metricas financieras insuficientes o no verificables")
        if task.approval_policy in {ApprovalPolicy.ALWAYS, ApprovalPolicy.MANUAL} or (
            task.approval_policy == ApprovalPolicy.SENSITIVE and task.requires_review
            and task.executor != ExecutorType.SIMULATED
        ):
            return ReviewDecision("needs_human", score, "La politica exige revision humana")
        if task.approval_policy == ApprovalPolicy.MILESTONE and "milestone" in task.tags:
            return ReviewDecision("needs_human", score, "Hito requiere revision humana")
        if successful:
            return ReviewDecision("approved", score, "Exit code, validaciones y artefactos correctos")
        return ReviewDecision("retry", score, "La ejecucion o las validaciones fallaron")

    @staticmethod
    def _metrics_pass(task: Task, metrics: dict) -> bool:
        if not metrics or not all(metrics.get(key) for key in ("data_is_real", "costs_included", "out_of_sample")):
            return False
        target_return = task.metadata.get("target_return")
        max_drawdown = task.metadata.get("max_drawdown")
        return (target_return is None or metrics.get("total_return", -1) >= target_return) and (
            max_drawdown is None or metrics.get("max_drawdown", 1) <= max_drawdown
        )
