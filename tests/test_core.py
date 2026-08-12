from orchestrator.adapters.storage import TaskStore
from orchestrator.application.worker import Worker
from orchestrator.domain.models import ExecutorType, TaskStatus, Task


def test_simulated_task_lifecycle(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    task = store.add(Task(prompt="smoke test", executor=ExecutorType.SIMULATED))
    assert Worker(store).run_once() == 0
    assert store.get_result(task.id).status == TaskStatus.SUCCEEDED
    assert store.get(task.id).status == TaskStatus.SUCCEEDED
