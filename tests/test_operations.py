from orchestrator.adapters.storage import TaskStore
from orchestrator.application.security import validate_task
from orchestrator.application.worker import Worker, evaluate_result, _ValidationOutcome
from orchestrator.domain.models import ApprovalPolicy, ExecutorType, Task, TaskResult, TaskStatus


def test_cancel_queued_task(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    task = store.add(Task(prompt="cancel me"))
    assert store.cancel(task.id)
    assert store.get(task.id).status == TaskStatus.CANCELLED


def test_security_rejects_always_approval_without_dry_run():
    task = Task(prompt="danger", approval_policy=ApprovalPolicy.ALWAYS)
    assert validate_task(task)


def test_worker_respects_priority(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    low = store.add(Task(prompt="low", priority=20, executor=ExecutorType.SIMULATED))
    high = store.add(Task(prompt="high", priority=1, executor=ExecutorType.SIMULATED))
    Worker(store).run_once()
    assert store.get_result(high.id).status == TaskStatus.SUCCEEDED
    assert store.get_result(low.id) is None


def test_validation_timeout_is_capped(monkeypatch, tmp_path):
    captured = {}

    def fake_run(command, cwd, timeout):
        captured["timeout"] = timeout
        return _ValidationOutcome(exit_code=0, stdout="", stderr="", timed_out=False)

    monkeypatch.setattr("orchestrator.application.worker._run_validation_process", fake_run)
    task = Task(prompt="validate", workspace=str(tmp_path),
                validation_commands=[["python", "check.py"]], timeout_seconds=900)
    result = evaluate_result(task, TaskResult(task_id=task.id, status=TaskStatus.SUCCEEDED))

    assert result.status == TaskStatus.SUCCEEDED
    assert captured["timeout"] == 300
