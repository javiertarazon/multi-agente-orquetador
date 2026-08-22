from orchestrator.domain.models import ExecutorType, Task, TaskResult, TaskStatus
from orchestrator.harness import ExecutionHarness, HarnessPolicy


def test_harness_normalizes_result_and_captures_exception():
    task = Task(prompt="x", executor=ExecutorType.SIMULATED)
    harness = ExecutionHarness(HarnessPolicy(max_output_bytes=4))
    result = harness.run(task, lambda _task: (_ for _ in ()).throw(RuntimeError("boom")))
    assert result.status == TaskStatus.FAILED
    assert "RuntimeError" in result.stderr


def test_harness_rejects_overlong_timeout():
    task = Task(prompt="x", timeout_seconds=901)
    result = ExecutionHarness().run(task, lambda _task: TaskResult(
        task_id=task.id, status=TaskStatus.SUCCEEDED))
    assert result.status == TaskStatus.FAILED
    assert "maximo" in result.stderr
