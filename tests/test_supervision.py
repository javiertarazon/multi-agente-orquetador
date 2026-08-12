from orchestrator.adapters.storage import TaskStore
from orchestrator.application.worker import Worker
from orchestrator.domain.models import ExecutorType, Task, TaskStatus
from orchestrator.domain.models import TaskResult
from orchestrator.adapters.executors import ClineExtensionExecutor


def test_failed_validation_is_retried_and_notified(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    task = store.add(Task(prompt="must be corrected", executor=ExecutorType.SIMULATED,
                          validation_commands=[["python", "-c", "raise SystemExit(1)"]],
                          max_retries=1))
    assert Worker(store).run_once() == 1
    assert store.get(task.id).status == TaskStatus.QUEUED
    assert any(item.event == "task_retry" for item in store.notifications(task.id))
    assert Worker(store).run_once() == 1
    assert store.get(task.id).status == TaskStatus.FAILED
    assert any(item.event == "task_failed" for item in store.notifications(task.id))


def test_success_generates_completion_notification(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    task = store.add(Task(prompt="ok", executor=ExecutorType.SIMULATED,
                          validation_commands=[["python", "-c", "print('ok')"]]))
    assert Worker(store).run_once() == 0
    assert any(item.event == "task_completed" for item in store.notifications(task.id))


def test_external_executor_waits_for_copilot_review(tmp_path, monkeypatch):
    store = TaskStore(str(tmp_path / "tasks.db"))
    task = store.add(Task(prompt="implement paper adapter", executor=ExecutorType.KILO))

    class SuccessfulExecutor:
        def run(self, task):
            return TaskResult(task_id=task.id, status=TaskStatus.SUCCEEDED, summary="implementado")

    monkeypatch.setattr("orchestrator.application.worker.executor_for", lambda _: SuccessfulExecutor())
    assert Worker(store).run_once() == 1
    assert store.get(task.id).status == TaskStatus.AWAITING_APPROVAL
    assert store.review(task.id, approved=True).status == TaskStatus.QUEUED
    assert store.get(task.id).review_status == "approved"


def test_cline_extension_executor_uses_configured_cli(monkeypatch):
    monkeypatch.setenv("MAOQ_CLINE_BIN", "cline-test")
    monkeypatch.setattr("orchestrator.adapters.executors.subprocess.run",
                        lambda *args, **kwargs: type("Completed", (), {
                            "returncode": 0, "stdout": "ok", "stderr": ""
                        })())
    result = ClineExtensionExecutor().run(Task(prompt="review code", executor=ExecutorType.CLINE))
    assert result.status == TaskStatus.SUCCEEDED
    assert result.stdout == "ok"