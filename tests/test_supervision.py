from datetime import UTC, datetime, timedelta

from orchestrator.adapters.executors import ClineExtensionExecutor
from orchestrator.adapters.storage import TaskStore
from orchestrator.application.artifact_scanner import ArtifactScanner
from orchestrator.application.auto_reviewer import AutoReviewer
from orchestrator.application.learning_engine import LearningEngine
from orchestrator.application.worker import Worker
from orchestrator.domain.models import ApprovalPolicy, ExecutorType, Task, TaskResult, TaskStatus
from orchestrator.interfaces.mcp.server import create_plan


def test_failed_validation_is_retried_and_notified(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    task = store.add(Task(prompt="must be corrected", executor=ExecutorType.SIMULATED,
                          validation_commands=[["python", "-c", "raise SystemExit(1)"]],
                          max_retries=1, backoff_base=0))
    assert Worker(store).run_once() == 1
    assert store.get(task.id).status == TaskStatus.RETRY_WAIT
    assert any(item.event == "task_retry_scheduled" for item in store.notifications(task.id))
    assert Worker(store).run_once() == 1
    assert store.get(task.id).status == TaskStatus.FAILED
    assert any(item.event == "task_failed" for item in store.notifications(task.id))


def test_retry_wait_executes_the_configured_retry(tmp_path, monkeypatch):
    store = TaskStore(str(tmp_path / "tasks.db"))
    task = store.add(Task(prompt="retry once", executor=ExecutorType.KILO,
                          max_retries=1, backoff_base=0))
    calls = []

    class FailingThenSuccessfulExecutor:
        def run(self, current_task):
            calls.append(current_task.retry_count)
            status = TaskStatus.FAILED if len(calls) == 1 else TaskStatus.SUCCEEDED
            return TaskResult(task_id=current_task.id, status=status, summary="attempt")

    monkeypatch.setattr("orchestrator.application.worker.executor_for",
                        lambda _: FailingThenSuccessfulExecutor())
    assert Worker(store).run_once() == 1
    assert store.get(task.id).status == TaskStatus.RETRY_WAIT
    assert Worker(store).run_once() == 1
    assert calls == [0, 1]
    assert store.get(task.id).status == TaskStatus.AWAITING_APPROVAL


def test_validation_runs_in_task_workspace(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    task = store.add(Task(prompt="validate workspace", workspace=str(workspace),
                          executor=ExecutorType.SIMULATED,
                          validation_commands=[["python", "-c",
                                                "from pathlib import Path; Path('marker.txt').write_text('ok')"]]))
    assert Worker(store).run_once() == 0
    assert (workspace / "marker.txt").read_text() == "ok"
    assert store.get(task.id).status == TaskStatus.SUCCEEDED


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
    assert store.review(task.id, approved=True).status == TaskStatus.SUCCEEDED
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


def test_stale_running_task_is_recovered(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    task = store.add(Task(prompt="recover me", status=TaskStatus.RUNNING,
                          max_retries=1, backoff_base=0,
                          updated_at=datetime.now(UTC) - timedelta(minutes=10)))
    assert store.recover_stale_running(max_age_seconds=60) == [task.id]
    assert store.get(task.id).status == TaskStatus.RETRY_WAIT
    assert any(item.event == "task_recovered" for item in store.notifications(task.id))


def test_plan_preserves_execution_controls(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = create_plan("controls", [{"prompt": "small", "executor": "simulated",
                                       "timeout_seconds": 17, "max_retries": 2,
                                       "dry_run": True}], auto_execute=False)
    task_store = TaskStore(result["database"])
    task = task_store.get(result["task_ids"][0])
    assert task.timeout_seconds == 17
    assert task.max_retries == 2
    assert task.dry_run is True


def test_artifact_scanner_records_allowed_change(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("before", encoding="utf-8")
    task = Task(prompt="change", workspace=str(tmp_path), allowed_paths=[str(target)])
    scanner = ArtifactScanner(task)
    scanner.capture_baseline()
    target.write_text("after", encoding="utf-8")
    artifacts = scanner.scan()
    assert len(artifacts) == 1
    assert artifacts[0].modification_type == "modified"
    assert artifacts[0].hash_sha256


def test_artifact_scanner_flags_change_outside_allowed_paths(tmp_path):
    allowed = tmp_path / "allowed.txt"
    blocked = tmp_path / "blocked.txt"
    allowed.write_text("stable", encoding="utf-8")
    blocked.write_text("before", encoding="utf-8")
    scanner = ArtifactScanner(Task(prompt="change", workspace=str(tmp_path), allowed_paths=[str(allowed)]))
    scanner.capture_baseline()
    blocked.write_text("after", encoding="utf-8")
    artifacts = scanner.scan()
    assert len(artifacts) == 1
    assert not artifacts[0].is_within_allowed_paths


def test_learning_engine_persists_timeout_episode(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    task = Task(prompt="small task", plan_id="plan", executor=ExecutorType.SIMULATED)
    result = TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=124, stderr="timeout")
    episode = LearningEngine(store).record_failure(task, result)
    assert episode.error_category == "timeout"
    assert store.similar_episodes("plan", "timeout")[0].id == episode.id


def test_auto_reviewer_rejects_unverified_financial_result():
    task = Task(prompt="metrics", approval_policy=ApprovalPolicy.AUTO_ON_PASS,
                metadata={"target_return": 0.55, "max_drawdown": 0.20})
    result = TaskResult(task_id=task.id, status=TaskStatus.SUCCEEDED, financial_metrics={
        "data_is_real": False, "costs_included": True, "out_of_sample": True,
        "total_return": 1.0, "max_drawdown": 0.1
    })
    assert AutoReviewer().review(task, result, []).verdict == "rejected"