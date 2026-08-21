from __future__ import annotations

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from orchestrator.adapters.config import load_settings
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
        settings = load_settings()
        selected = order or _resolve_order(settings.fallback_order)
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

    def swarm_round(self, request: AgentRequest) -> tuple[TaskResult, str]:
        """Ejecuta el mismo prompt en paralelo con kilo, hermes y cline.

        Solo se activa si la tarea lleva el tag `enjambre`. Devuelve el resultado
        con la salida mas larga y el nombre del ganador. Si la ejecucion paralela
        falla o nadie triunfa, cae al fallback normal (`execute`).
        """
        if not any("enjambre" in tag.lower() for tag in request.task.tags):
            return self.execute(request)
        worker_kinds = [ExecutorType.KILO, ExecutorType.HERMES, ExecutorType.CLINE]
        providers = [ExecutorProvider(kind) for kind in worker_kinds]
        with ThreadPoolExecutor(max_workers=len(providers)) as pool:
            futures = {pool.submit(provider.execute, request): provider.name for provider in providers}
            outcomes: dict[str, TaskResult | None] = {}
            for future, name in futures.items():
                try:
                    outcomes[name] = future.result()
                except Exception:  # noqa: BLE001 - el round no debe morir por un worker
                    outcomes[name] = None
        winners = {name: result for name, result in outcomes.items()
                   if result and result.status.value == "succeeded"}
        if not winners:
            return self.execute(request)

        def _length(result: TaskResult) -> int:
            return len(result.stdout or "") + len(result.summary or "")

        winner = max(winners, key=lambda name: _length(winners[name]))
        return winners[winner], winner


def _resolve_order(names: list[str]) -> list[ExecutorType]:
    by_name = {executor.value: executor for executor in ExecutorType}
    return [by_name[name] for name in names if name in by_name] or list(ExecutorType)
