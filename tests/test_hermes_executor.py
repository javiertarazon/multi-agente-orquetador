from orchestrator.adapters.executors import (
    _HERMES_FAILURE_SIGNATURES,
    HermesExecutor,
    _contains_failure_signature,
    _SubprocessOutcome,
)
from orchestrator.domain.models import ExecutorType, Task, TaskStatus


def _task(prompt="haz algo") -> Task:
    return Task(prompt=prompt, executor=ExecutorType.HERMES)


def _fake_run(stdout="", stderr="", returncode=0, timed_out=False):
    def _fake(*args, **kwargs):
        return _SubprocessOutcome(stdout=stdout, stderr=stderr,
                                  returncode=returncode, timed_out=timed_out)
    return _fake


def test_hermes_build_command_defaults(monkeypatch):
    monkeypatch.delenv("MAOQ_HERMES_MODEL", raising=False)
    monkeypatch.delenv("MAOQ_HERMES_PROVIDER", raising=False)
    executor = HermesExecutor()
    executor.executable = "hermes"
    command = executor._build_command(_task())
    assert command[0] == "hermes"
    assert command[1] == "-z"
    assert command[2] == "haz algo"
    assert command[-2:] == ["--accept-hooks", "--yolo"]
    # Hermes usa su configuración nativa cuando no hay override explícito.
    assert command[3:7] == ["--provider", "nvidia", "--model", "nvidia/nemotron-3-ultra-550b-a55b"]


def test_hermes_build_command_with_model_and_provider(monkeypatch):
    monkeypatch.setenv("MAOQ_HERMES_MODEL", "gemini-3.6-flash")
    monkeypatch.setenv("MAOQ_HERMES_PROVIDER", "gemini")
    executor = HermesExecutor()
    executor.executable = "hermes"
    command = executor._build_command(_task())
    assert "--provider" in command
    assert command[command.index("--provider") + 1] == "gemini"
    assert "--model" in command
    assert command[command.index("--model") + 1] == "gemini-3.6-flash"


def test_hermes_build_command_wraps_cmd_on_windows(monkeypatch):
    executor = HermesExecutor()
    executor.executable = "C:/Users/javier/.local/bin/hermes.CMD"
    command = executor._build_command(_task("tarea con espacios y 'comillas'"))
    assert command[0] == "cmd"
    assert command[1] == "/c"
    assert command[2] == "C:/Users/javier/.local/bin/hermes.CMD"


def test_hermes_success(monkeypatch):
    monkeypatch.setattr("orchestrator.adapters.executors._run_agent_process",
                        _fake_run(stdout="respuesta final OK"))
    result = HermesExecutor().run(_task())
    assert result.status == TaskStatus.SUCCEEDED
    assert "respuesta final OK" in result.stdout


def test_hermes_empty_stdout_is_failure(monkeypatch):
    monkeypatch.setattr("orchestrator.adapters.executors._run_agent_process",
                        _fake_run(stdout=""))
    result = HermesExecutor().run(_task())
    assert result.status == TaskStatus.FAILED
    assert "respuesta vacia" in result.summary


def test_hermes_http_404_is_failure(monkeypatch):
    monkeypatch.setattr("orchestrator.adapters.executors._run_agent_process",
                        _fake_run(stdout="API call failed after 3 retries: HTTP 404: 404 page not found"))
    result = HermesExecutor().run(_task())
    assert result.status == TaskStatus.FAILED
    assert "HTTP 404" in result.stdout


def test_hermes_nonzero_exit_is_failure(monkeypatch):
    monkeypatch.setattr("orchestrator.adapters.executors._run_agent_process",
                        _fake_run(stdout="salida con texto", returncode=1))
    result = HermesExecutor().run(_task())
    assert result.status == TaskStatus.FAILED


def test_hermes_returns_task_result(monkeypatch):
    monkeypatch.setattr("orchestrator.adapters.executors._run_agent_process",
                        _fake_run(stdout="respuesta final OK"))
    result = HermesExecutor().run(_task())
    assert result.task_id is not None
    assert result.status == TaskStatus.SUCCEEDED
    assert result.duration_seconds is not None


def test_hermes_timeout_is_failure(monkeypatch):
    monkeypatch.setattr("orchestrator.adapters.executors._run_agent_process",
                        _fake_run(timed_out=True))
    result = HermesExecutor().run(_task())
    assert result.status == TaskStatus.FAILED
    assert result.exit_code == 124


def test_failure_signature_detection():
    assert _contains_failure_signature("HTTP 429: rate limited")
    assert _contains_failure_signature("models/gemini-2.0-flash is no longer available")
    assert not _contains_failure_signature("respuesta normal")
    for signature in _HERMES_FAILURE_SIGNATURES:
        assert _contains_failure_signature(signature), signature
