from pathlib import Path

from orchestrator.adapters.agent_gateway import AgentGateway, AgentRequest
from orchestrator.application.security import validate_task
from orchestrator.domain.models import (
    AgentCapabilities,
    ExecutorType,
    PlanContract,
    Task,
    TaskResult,
    TaskStatus,
    TokenBudget,
)


def test_contracts_have_safe_defaults_and_round_trip() -> None:
    plan = PlanContract(objective="validar estrategia")
    budget = TokenBudget()
    assert plan.schema_version == "1.0"
    assert plan.dry_run is True
    assert plan.executor_order[0] == ExecutorType.KILO
    assert TokenBudget.model_validate_json(budget.model_dump_json()).max_attempts == 3


def test_live_trading_is_rejected() -> None:
    task = Task(prompt="operar", metadata={"live_trading": True})
    assert any("live_trading" in problem for problem in validate_task(task))


def test_invalid_token_budget_is_rejected() -> None:
    task = Task(prompt="probar", metadata={"token_budget": {"max_attempts": 0}})
    assert any("token_budget invalido" in problem for problem in validate_task(task))


def test_gateway_executes_simulated_provider() -> None:
    task = Task(prompt="tarea", executor=ExecutorType.SIMULATED, workspace=str(Path.cwd()))
    result, provider = AgentGateway([ExecutorType.SIMULATED]).execute(AgentRequest(task))
    assert provider == "simulated"
    assert result.status == TaskStatus.SUCCEEDED


def test_capabilities_are_serializable() -> None:
    capabilities = AgentCapabilities(provider="cline")
    assert capabilities.model_dump(mode="json")["free_model"] is True


def test_gateway_returns_last_failure_without_silent_success(monkeypatch) -> None:
    class FailedExecutor:
        def run(self, task: Task) -> TaskResult:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=127,
                              summary="provider unavailable")

    monkeypatch.setattr("orchestrator.adapters.agent_gateway.executor_for", lambda _: FailedExecutor())
    task = Task(prompt="tarea", executor=ExecutorType.KILO)
    result, provider = AgentGateway([ExecutorType.KILO]).execute(AgentRequest(task))
    assert provider == "kilo"
    assert result.status == TaskStatus.FAILED
