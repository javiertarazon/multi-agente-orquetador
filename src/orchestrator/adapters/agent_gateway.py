from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from orchestrator.adapters.executors import executor_for
from orchestrator.domain.models import AgentCapabilities, ExecutorType, Task, TaskResult


@dataclass(frozen=True)
class AgentRequest:
    task: Task
    context: str = ""


class AgentProvider(ABC):
    """Contrato común para Kilo, Cline y futuros proveedores headless."""

    name: str

    @abstractmethod
    def capabilities(self) -> AgentCapabilities:
        raise NotImplementedError

    @abstractmethod
    def execute(self, request: AgentRequest) -> TaskResult:
        raise NotImplementedError


class ExecutorProvider(AgentProvider):
    def __init__(self, kind: ExecutorType) -> None:
        self.kind = kind
        self.name = kind.value
        self._executor = executor_for(kind)

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(provider=self.name, free_model=self.kind != ExecutorType.SIMULATED)

    def execute(self, request: AgentRequest) -> TaskResult:
        task = request.task.model_copy(deep=True)
        if request.context:
            task.prompt = f"{task.prompt}\n\nContexto relevante:\n{request.context}"
        return self._executor.run(task)


class AgentGateway:
    """Selecciona proveedores sin acoplar el supervisor a un CLI concreto."""

    def __init__(self, order: list[ExecutorType] | None = None) -> None:
        selected = order or [ExecutorType.KILO, ExecutorType.CLINE, ExecutorType.SIMULATED]
        self.providers = [ExecutorProvider(kind) for kind in selected]

    def execute(self, request: AgentRequest) -> tuple[TaskResult, str]:
        last: TaskResult | None = None
        for provider in self.providers:
            result = provider.execute(request)
            last = result
            if result.status.value == "succeeded" or provider.kind == ExecutorType.SIMULATED:
                return result, provider.name
        assert last is not None
        return last, self.providers[-1].name
