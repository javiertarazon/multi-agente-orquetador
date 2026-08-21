from types import SimpleNamespace

from orchestrator.adapters.agent_gateway import AgentGateway, AgentRequest
from orchestrator.adapters.storage import TaskStore
from orchestrator.application.auto_reviewer import AutoReviewer
from orchestrator.application.learning_engine import LearningEngine
from orchestrator.domain.models import ExecutorType, Task, TaskResult, TaskStatus
from orchestrator.interfaces.mcp.server import create_plan, resume_plan, session_summary


def _task(prompt="p") -> Task:
    return Task(prompt=prompt, executor=ExecutorType.SIMULATED)


def test_cross_review_rejects_claims_without_changes():
    result = TaskResult(task_id="t", status=TaskStatus.SUCCEEDED,
                        summary="Se implemento la funcionalidad solicitada")
    assert AutoReviewer().cross_review(_task(), result, []) == "rejected"


def test_cross_review_needs_human_on_empty_summary():
    result = TaskResult(task_id="t", status=TaskStatus.SUCCEEDED, summary="")
    assert AutoReviewer().cross_review(_task(), result, []) == "needs_human"


def test_cross_review_needs_human_on_generic_short_summary():
    result = TaskResult(task_id="t", status=TaskStatus.SUCCEEDED, summary="ok")
    assert AutoReviewer().cross_review(_task(), result, []) == "needs_human"


def test_cross_review_approved_with_changes():
    result = TaskResult(task_id="t", status=TaskStatus.SUCCEEDED,
                        summary="Se implemento el modulo X con tests",
                        changed_files=["src/x.py"])
    assert AutoReviewer().cross_review(_task(), result, []) == "approved"


def test_cross_review_approved_without_claims_with_changes():
    result = TaskResult(task_id="t", status=TaskStatus.SUCCEEDED,
                        summary="Tarea completada correctamente con resultados validados",
                        changed_files=["src/x.py"])
    assert AutoReviewer().cross_review(_task(), result, []) == "approved"


def test_lessons_returns_phrases_from_episodes(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    engine = LearningEngine(store)
    engine.record_failure(
        Task(prompt="p", plan_id="plan", executor=ExecutorType.SIMULATED),
        TaskResult(task_id="t", status=TaskStatus.FAILED, exit_code=124, stderr="timeout"),
    )
    frases = engine.lessons("plan")
    assert len(frases) == 1
    assert "timeout" in frases[0]
    assert "fallo por" in frases[0]


def test_lessons_honors_limit(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    engine = LearningEngine(store)
    for index in range(3):
        engine.record_failure(
            Task(prompt="p", plan_id="plan", executor=ExecutorType.SIMULATED),
            TaskResult(task_id=f"t{index}", status=TaskStatus.FAILED,
                       exit_code=124, stderr="timeout"),
        )
    assert len(engine.lessons("plan", limit=1)) == 1
    assert len(engine.lessons("plan", limit=3)) == 3


def test_create_plan_prepends_previous_lessons(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    previo = create_plan("primer plan", [{"prompt": "primero", "executor": "simulated"}],
                         auto_execute=False)
    prev_store = TaskStore(previo["database"])
    LearningEngine(prev_store).record_failure(
        Task(prompt="primero", plan_id=previo["plan_id"], executor=ExecutorType.SIMULATED),
        TaskResult(task_id=previo["task_ids"][0], status=TaskStatus.FAILED,
                   exit_code=124, stderr="timeout"),
    )
    nuevo = create_plan("segundo plan", [{"prompt": "segundo", "executor": "simulated"}],
                        auto_execute=False, lessons_from=previo["plan_id"])
    task = TaskStore(nuevo["database"]).get(nuevo["task_ids"][0])
    assert "LECCIONES PREVIAS" in task.metadata.get("plan", "")
    assert "timeout" in task.metadata.get("plan", "")


def test_session_summary_compact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plan = create_plan("objetivo", [{"prompt": "tarea pendiente " + "x" * 200,
                                     "executor": "simulated"}], auto_execute=False)
    resumen = session_summary(plan["plan_id"], limit=5)
    assert resumen["total"] == 1
    assert resumen["by_status"]["queued"] == 1
    assert len(resumen["pendientes"]) == 1
    assert len(resumen["pendientes"][0]["prompt"]) <= 123
    assert resumen["pendientes"][0]["prompt"].endswith("...")


def test_resume_plan_requeues_only_non_terminal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plan = create_plan("objetivo", [
        {"prompt": "a", "executor": "simulated"},
        {"prompt": "b", "executor": "simulated"},
    ], auto_execute=False)
    plan_store = TaskStore(plan["database"])
    plan_store.update_result(TaskResult(task_id=plan["task_ids"][0],
                                        status=TaskStatus.SUCCEEDED, summary="hecho"))
    resultado = resume_plan(plan["plan_id"])
    assert resultado["reencoladas"] == 1
    assert plan_store.get(plan["task_ids"][0]).status.value == "succeeded"
    # resume_plan starts the supervisor immediately; the task can be queued
    # briefly or already claimed by the worker.
    assert plan_store.get(plan["task_ids"][1]).status.value in {"queued", "running"}


def _fake_executor_factory(records):
    def factory(kind):
        def run(task):
            records.append(kind.value)
            lengths = {ExecutorType.KILO: 3, ExecutorType.HERMES: 5, ExecutorType.CLINE: 2}
            return TaskResult(task_id=task.id, status=TaskStatus.SUCCEEDED,
                              summary="x" * lengths[kind])
        return SimpleNamespace(run=run)
    return factory


def test_swarm_round_runs_three_executors_and_picks_longest(monkeypatch):
    records = []
    monkeypatch.setattr("orchestrator.adapters.agent_gateway.executor_for",
                        _fake_executor_factory(records))
    gateway = AgentGateway()
    records.clear()
    result, winner = gateway.swarm_round(AgentRequest(task=Task(prompt="p", tags=["enjambre"])))
    assert set(records) == {"kilo", "hermes", "cline"}
    assert winner == "hermes"
    assert len(result.summary) == 5


def test_swarm_round_without_tag_uses_normal_execute(monkeypatch):
    records = []
    monkeypatch.setattr("orchestrator.adapters.agent_gateway.executor_for",
                        _fake_executor_factory(records))
    gateway = AgentGateway()
    records.clear()
    _result, winner = gateway.swarm_round(AgentRequest(task=_task()))
    assert records == ["kilo"]
    assert winner == "kilo"


def test_swarm_round_falls_back_when_parallel_execution_fails(monkeypatch):
    def factory(kind):
        def run(task):
            if kind == ExecutorType.SIMULATED:
                return TaskResult(task_id=task.id, status=TaskStatus.SUCCEEDED, summary="sim")
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, summary="fallo")
        return SimpleNamespace(run=run)
    monkeypatch.setattr("orchestrator.adapters.agent_gateway.executor_for", factory)
    gateway = AgentGateway()
    result, winner = gateway.swarm_round(AgentRequest(task=Task(prompt="p", tags=["enjambre"])))
    assert winner == "simulated"
    assert result.summary == "sim"
