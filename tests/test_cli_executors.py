from orchestrator.adapters.executors import (
    ClineExecutor,
    KiloExecutor,
    _extract_json_text,
    _SubprocessOutcome,
    _run_agent_process,
)
import sys
import time
from orchestrator.domain.models import ExecutorType, Task, TaskStatus


def _task(prompt="haz algo") -> Task:
    return Task(prompt=prompt, executor=ExecutorType.KILO)


def _fake_run(stdout="", stderr="", returncode=0, timed_out=False):
    def _fake(*a, **k):
        return _SubprocessOutcome(stdout=stdout, stderr=stderr,
                                  returncode=returncode, timed_out=timed_out)
    return _fake


def test_kilo_build_command_uses_run_json_and_free_model(monkeypatch):
    monkeypatch.delenv("MAOQ_KILO_BIN", raising=False)
    monkeypatch.delenv("MAOQ_KILO_MODEL", raising=False)
    executor = KiloExecutor()
    executor.executable = "kilo"
    command = executor._build_command(_task())
    assert command[0] == "kilo"
    assert command[1] == "run"
    assert "--format" in command
    assert command[command.index("--format") + 1] == "json"
    assert "--model" in command
    assert command[command.index("--model") + 1] == "kilo/cohere/north-mini-code:free"
    assert command[-1] == "haz algo"


def test_kilo_build_command_wraps_cmd_on_windows(monkeypatch):
    executor = KiloExecutor()
    executor.executable = "C:/Users/javier/AppData/Roaming/npm/kilo.CMD"
    command = executor._build_command(_task())
    assert command[0] == "cmd"
    assert command[1] == "/c"


def test_kilo_success_extracts_json_text(monkeypatch):
    stdout = (
        '{"type":"step_start","part":{}}\n'
        '{"type":"text","part":{"text":"respuesta OK"}}\n'
        '{"type":"step_finish","part":{"reason":"stop"}}\n'
    )
    monkeypatch.setattr(
        "orchestrator.adapters.executors._run_agent_process",
        _fake_run(stdout=stdout),
    )
    result = KiloExecutor().run(_task())
    assert result.status == TaskStatus.SUCCEEDED
    assert "respuesta OK" in result.summary


def test_kilo_empty_output_is_failure(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.adapters.executors._run_agent_process",
        _fake_run(stdout=""),
    )
    result = KiloExecutor().run(_task())
    assert result.status == TaskStatus.FAILED
    assert "respuesta vacia" in result.summary


def test_kilo_nonzero_exit_is_failure(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.adapters.executors._run_agent_process",
        _fake_run(stdout='{"type":"text","part":{"text":"parcial"}}',
                  returncode=1, stderr="error"),
    )
    result = KiloExecutor().run(_task())
    assert result.status == TaskStatus.FAILED


def test_kilo_timeout_is_failure(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.adapters.executors._run_agent_process",
        _fake_run(timed_out=True),
    )
    result = KiloExecutor().run(_task())
    assert result.status == TaskStatus.FAILED
    assert result.exit_code == 124


def test_cline_build_command_uses_native_provider_model(monkeypatch):
    monkeypatch.delenv("MAOQ_CLINE_BIN", raising=False)
    monkeypatch.delenv("MAOQ_CLINE_MODEL", raising=False)
    monkeypatch.delenv("MAOQ_CLINE_PROVIDER", raising=False)
    monkeypatch.delenv("GOOGLE_GENERATIVE_AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    executor = ClineExecutor()
    executor.executable = "cline"
    command = executor._build_command(_task())
    assert command[0] == "cline"
    assert command[1] == "--json"
    assert "--auto-approve" in command
    assert "-P" in command
    assert command[command.index("-P") + 1] == "cline"
    assert "-m" in command
    assert command[command.index("-m") + 1] == "anthropic/claude-sonnet-5"
    assert "-k" not in command


def test_cline_build_command_injects_key_for_nvidia(monkeypatch):
    monkeypatch.setenv("MAOQ_CLINE_PROVIDER", "nvidia")
    monkeypatch.setenv("MAOQ_CLINE_MODEL", "nvidia/nemotron-3-super-120b-a12b")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-secret")
    executor = ClineExecutor()
    executor.executable = "cline"
    command = executor._build_command(_task())
    assert "-k" in command
    assert command[command.index("-k") + 1] == "nvapi-secret"


def test_cline_build_command_injects_key_for_gemini(monkeypatch):
    monkeypatch.setenv("MAOQ_CLINE_PROVIDER", "gemini")
    monkeypatch.setenv("MAOQ_CLINE_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GOOGLE_GENERATIVE_AI_API_KEY", "secret-key")
    executor = ClineExecutor()
    executor.executable = "cline"
    command = executor._build_command(_task())
    assert "-k" in command
    assert command[command.index("-k") + 1] == "secret-key"


def test_cline_build_command_injects_openrouter_key(monkeypatch):
    monkeypatch.setenv("MAOQ_CLINE_PROVIDER", "openrouter")
    monkeypatch.setenv("MAOQ_CLINE_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-secret")
    monkeypatch.delenv("GOOGLE_GENERATIVE_AI_API_KEY", raising=False)
    executor = ClineExecutor()
    executor.executable = "cline"
    command = executor._build_command(_task())
    assert "-k" in command
    assert command[command.index("-k") + 1] == "sk-openrouter-secret"


def test_cline_success_extracts_run_result_text(monkeypatch):
    stdout = (
        '{"ts":"1","type":"agent_event","event":{"type":"text","contentType":"text","text":"O"}}\n'
        '{"ts":"2","type":"agent_event","event":{"type":"text","contentType":"text","text":"K"}}\n'
        '{"ts":"3","type":"run_result","finishReason":"completed","text":"OK","usage":{}}\n'
    )
    monkeypatch.setattr(
        "orchestrator.adapters.executors._run_agent_process",
        _fake_run(stdout=stdout),
    )
    result = ClineExecutor().run(_task())
    assert result.status == TaskStatus.SUCCEEDED
    assert result.summary == "OK"


def test_cline_nonzero_exit_is_failure(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.adapters.executors._run_agent_process",
        _fake_run(stdout="", returncode=1, stderr="boom"),
    )
    result = ClineExecutor().run(_task())
    assert result.status == TaskStatus.FAILED
    assert "codigo 1" in result.summary


def test_extract_json_text_handles_mixed_and_invalid_lines():
    payload = (
        'not json\n'
        '{"type":"text","part":{"text":"uno"}}\n'
        'garbage\n'
        '{"type":"run_result","text":"final"}\n'
    )
    assert _extract_json_text(payload) == "final"


def test_extract_json_text_uses_done_text():
    payload = '{"type":"done","reason":"completed","text":"listo"}\n'
    assert _extract_json_text(payload) == "listo"


def test_agent_process_timeout_is_bounded_on_windows():
    started = time.monotonic()
    outcome = _run_agent_process(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=".",
        timeout=0.2,
    )
    elapsed = time.monotonic() - started
    assert outcome.timed_out is True
    assert outcome.returncode != 0
    assert elapsed < 8
