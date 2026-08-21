from orchestrator.adapters.config import AgentConfig, load_settings
from orchestrator.adapters.storage import TaskStore
from orchestrator.application.learning_engine import LearningEngine
from orchestrator.domain.models import ExecutorType, Task, TaskResult, TaskStatus


def test_load_settings_reads_yaml_config(monkeypatch):
    monkeypatch.delenv("MAOQ_KILO_MODEL", raising=False)
    monkeypatch.delenv("MAOQ_HERMES_MODEL", raising=False)
    monkeypatch.delenv("MAOQ_HERMES_PROVIDER", raising=False)
    monkeypatch.delenv("MAOQ_CLINE_MODEL", raising=False)
    monkeypatch.delenv("MAOQ_CLINE_PROVIDER", raising=False)
    settings = load_settings()
    assert settings.kilo_model == "kilo/cohere/north-mini-code:free"
    assert settings.hermes_provider == "nvidia"
    assert settings.hermes_model == "nemotron-3-ultra-550b-a55b"
    assert settings.cline_provider == "cline"
    assert "kilo" in settings.agents
    assert settings.agents["cline"].role == "worker"


def test_load_settings_env_overrides_yaml(monkeypatch):
    monkeypatch.setenv("MAOQ_KILO_MODEL", "google/gemini-3.6-flash")
    monkeypatch.delenv("MAOQ_HERMES_MODEL", raising=False)
    monkeypatch.delenv("MAOQ_HERMES_PROVIDER", raising=False)
    monkeypatch.delenv("MAOQ_CLINE_MODEL", raising=False)
    monkeypatch.delenv("MAOQ_CLINE_PROVIDER", raising=False)
    assert load_settings().kilo_model == "google/gemini-3.6-flash"


def test_agent_config_defaults_are_safe():
    config = AgentConfig()
    assert config.role == "worker"
    assert config.capabilities == []


def test_get_episodes_returns_compact_memory(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    task = Task(prompt="tarea", plan_id="plan-1", executor=ExecutorType.SIMULATED)
    result = TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=124, stderr="timeout")
    LearningEngine(store).record_failure(task, result)
    episodes = store.episodes(plan_id="plan-1")
    assert len(episodes) == 1
    assert episodes[0].error_category == "timeout"
    assert store.episodes()  # lista global sin filtro
