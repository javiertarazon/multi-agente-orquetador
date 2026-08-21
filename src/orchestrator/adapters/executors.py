from __future__ import annotations

import json
import os
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from orchestrator.adapters.config import load_settings
from orchestrator.domain.models import ExecutorType, Task, TaskResult, TaskStatus


class Executor(ABC):
    kind: ExecutorType

    @abstractmethod
    def run(self, task: Task) -> TaskResult:
        raise NotImplementedError


@dataclass
class _SubprocessOutcome:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool
    not_found: str = ""


def _kill_tree(pid: int) -> None:
    """Mata un proceso y todo su arbol en Windows.

    En Windows el wrapper cmd /c lanza .cmd que a su vez lanza node/kilo.
    subprocess.run(timeout=...) solo mata cmd.exe, dejando los nietos
    huerfanos con los pipes heredados abiertos; communicate() espera el EOF
    para siempre y la tarea nunca transiciona de running. taskkill /T /F
    derriba el arbol completo.
    """
    try:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True, timeout=15, check=False,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass


def _run_agent_process(
    command: list[str],
    cwd: str,
    env: dict[str, str] | None = None,
    timeout: float = 600,
) -> _SubprocessOutcome:
    """Ejecuta un agente capturando salida con timeout robusto.

    A diferencia de subprocess.run(timeout=...), al expirar el timeout se
    derriba el arbol completo de procesos (taskkill /T /F) antes de volver a
    comunicar, evitando quedarse esperando EOF por procesos huerfanos.
    """
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=env,
            creationflags=creationflags,
        )
    except FileNotFoundError as error:
        return _SubprocessOutcome(stdout="", stderr=str(error), returncode=127,
                                  timed_out=False, not_found=str(error))
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return _SubprocessOutcome(
            stdout=stdout or "", stderr=stderr or "",
            returncode=proc.returncode, timed_out=False,
        )
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        try:
            stdout, stderr = proc.communicate(timeout=15)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            stdout, stderr = "", ""
        return _SubprocessOutcome(
            stdout=stdout or "", stderr=stderr or "",
            returncode=proc.returncode, timed_out=True,
        )


class SimulatedExecutor(Executor):
    kind = ExecutorType.SIMULATED

    def run(self, task: Task) -> TaskResult:
        return TaskResult(task_id=task.id, status=TaskStatus.SUCCEEDED,
                          summary=f"Tarea simulada completada: {task.prompt}")


class SubprocessExecutor(Executor):
    def __init__(self, command: list[str], kind: ExecutorType, auto_flag: list[str]) -> None:
        self.command = command
        self.kind = kind
        self.auto_flag = auto_flag

    def run(self, task: Task) -> TaskResult:
        started = time.monotonic()
        command = [*self.command, *self.auto_flag, task.prompt]
        outcome = _run_agent_process(command, task.workspace, timeout=task.timeout_seconds)
        if outcome.timed_out:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=124,
                summary="La tarea excedio el timeout", stderr="timeout")
        status = TaskStatus.SUCCEEDED if outcome.returncode == 0 else TaskStatus.FAILED
        return TaskResult(task_id=task.id, status=status, exit_code=outcome.returncode,
            summary=f"{self.kind.value} finalizo con codigo {outcome.returncode}",
            stdout=outcome.stdout[-20000:], stderr=outcome.stderr[-20000:],
            duration_seconds=round(time.monotonic() - started, 3))


def _inject_key(env: dict[str, str], name: str, default: str = "") -> dict[str, str]:
    """Copia la clave de la variable dada al subproceso, por si el CLI la lee."""
    value = os.environ.get(name) or default
    if value:
        env[name] = value
    return env


def _extract_json_text(stdout: str) -> str:
    """Extrae el texto final de una salida JSON de eventos CLI (kilo/cline)."""
    text = ""
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            continue
        event_type = event.get("type", event.get("event", {}).get("type", ""))
        if event_type == "text":
            text = event.get("part", {}).get("text", event.get("text", text)) or text
        elif event_type in ("done", "run_result"):
            event_text = event.get("text")
            if event_text:
                text = event_text
    return text.strip()


class KiloExecutor(Executor):
    """Ejecuta Kilo en modo headless: kilo run <prompt> --auto --format json.

    Kilo 7.x imprime eventos JSON por stdout; el texto final se extrae de esos
    eventos. La salida se guarda completa en stdout para auditoria y el resumen
    usa el texto extraido para reducir tokens.
    """

    kind = ExecutorType.KILO

    def __init__(self) -> None:
        settings = load_settings()
        self.executable = os.environ.get("MAOQ_KILO_BIN") or discover_kilo_binary()
        self.model = settings.kilo_model
        self.model_env = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""

    def _build_command(self, task: Task) -> list[str]:
        command = [self.executable, "run"]
        command.extend(["--auto", "--format", "json"])
        if self.model:
            command.extend(["--model", self.model])
        command.append(task.prompt)
        if self.executable.lower().endswith((".cmd", ".bat")):
            command = ["cmd", "/c", *command]
        return command

    def run(self, task: Task) -> TaskResult:
        started = time.monotonic()
        command = self._build_command(task)
        env = os.environ.copy()
        _inject_key(env, "GOOGLE_GENERATIVE_AI_API_KEY", self.model_env)
        _inject_key(env, "OPENROUTER_API_KEY")
        _inject_key(env, "NVIDIA_API_KEY")
        outcome = _run_agent_process(command, task.workspace, env=env,
                                     timeout=task.timeout_seconds)
        if outcome.not_found:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=127,
                summary=f"Ejecutable no encontrado: {self.executable}", stderr=outcome.not_found)
        if outcome.timed_out:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=124,
                summary="La tarea Kilo excedio el timeout", stderr="timeout")
        stdout = outcome.stdout
        text = _extract_json_text(stdout)
        failed = outcome.returncode != 0 or not text
        if failed:
            status = TaskStatus.FAILED
            summary = "kilo devolvio una respuesta vacia" if not text else f"kilo finalizo con codigo {outcome.returncode}"
        else:
            status = TaskStatus.SUCCEEDED
            summary = text[:2000]
        return TaskResult(task_id=task.id, status=status, exit_code=outcome.returncode,
            summary=summary, stdout=stdout[-20000:], stderr=outcome.stderr[-20000:],
            duration_seconds=round(time.monotonic() - started, 3))


class ClineExecutor(Executor):
    """Ejecuta Cline CLI headless: cline --json --auto-approve true.

    Usa el provider y modelo de config/default.yaml (por defecto nvidia con
    un modelo NVIDIA gratuito). La key se pasa via -k y tambien se inyecta como
    variable de entorno al subproceso segun el provider.
    """

    kind = ExecutorType.CLINE

    def __init__(self) -> None:
        settings = load_settings()
        self.executable = os.environ.get("MAOQ_CLINE_BIN") or discover_cline_binary()
        self.model = os.environ.get("MAOQ_CLINE_MODEL") or settings.cline_model
        self.provider = os.environ.get("MAOQ_CLINE_PROVIDER") or settings.cline_provider
        self.model_env = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
        self.openrouter_env = os.environ.get("OPENROUTER_API_KEY") or ""
        self.nvidia_env = os.environ.get("NVIDIA_API_KEY") or ""

    def _build_command(self, task: Task) -> list[str]:
        command = [self.executable, "--json", "--auto-approve", "true"]
        if self.provider:
            command.extend(["-P", self.provider])
        if self.model:
            command.extend(["-m", self.model])
        if self.provider == "gemini" and self.model_env:
            command.extend(["-k", self.model_env])
        elif self.provider == "openrouter" and self.openrouter_env:
            command.extend(["-k", self.openrouter_env])
        elif self.provider == "nvidia" and self.nvidia_env:
            command.extend(["-k", self.nvidia_env])
        command.extend(["--cwd", task.workspace, task.prompt])
        if self.executable.lower().endswith((".cmd", ".bat")):
            command = ["cmd", "/c", *command]
        return command

    def run(self, task: Task) -> TaskResult:
        started = time.monotonic()
        command = self._build_command(task)
        env = os.environ.copy()
        _inject_key(env, "GOOGLE_GENERATIVE_AI_API_KEY", self.model_env)
        _inject_key(env, "OPENROUTER_API_KEY")
        _inject_key(env, "NVIDIA_API_KEY")
        outcome = _run_agent_process(command, task.workspace, env=env,
                                     timeout=task.timeout_seconds)
        if outcome.not_found:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=127,
                summary=f"Ejecutable no encontrado: {self.executable}", stderr=outcome.not_found)
        if outcome.timed_out:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=124,
                summary="La tarea Cline excedio el timeout", stderr="timeout")
        stdout = outcome.stdout
        text = _extract_json_text(stdout)
        failed = outcome.returncode != 0
        if outcome.returncode == 0 and not text:
            text = stdout[-4000:]
        status = TaskStatus.SUCCEEDED if not failed else TaskStatus.FAILED
        summary = text[:2000] if not failed else (
            f"cline finalizo con codigo {outcome.returncode}")
        return TaskResult(task_id=task.id, status=status, exit_code=outcome.returncode,
            summary=summary, stdout=stdout[-20000:], stderr=outcome.stderr[-20000:],
            duration_seconds=round(time.monotonic() - started, 3))


class ClineExtensionExecutor(ClineExecutor):
    """Ejecuta Cline mediante un bridge externo cuando MAOQ_CLINE_BRIDGE existe.

    El bridge recibe el prompt como ultimo argumento y debe devolver codigo cero
    cuando termina correctamente. Sin bridge delegua en el CLI headless.
    """

    def __init__(self) -> None:
        bridge = os.environ.get("MAOQ_CLINE_BRIDGE")
        if bridge:
            self.bridge = bridge
            self.executable = bridge
        else:
            super().__init__()

    def _build_command(self, task: Task) -> list[str]:
        if getattr(self, "bridge", ""):
            return ["cmd", "/c", self.bridge, task.prompt] if self.bridge.lower().endswith((".cmd", ".bat")) else [self.bridge, task.prompt]
        return super()._build_command(task)


_HERMES_FAILURE_SIGNATURES = (
    "API call failed",
    "Add credits to continue",
    "HTTP 401",
    "HTTP 403",
    "HTTP 404",
    "HTTP 429",
    "no longer available",
    "not found",
    "Traceback (most recent call last)",
    "No Windows console found",
    "not recognized as",
    "hermes: error:",
)


class HermesExecutor(Executor):
    """Ejecuta Hermes en modo oneshot (-z) para tareas headless.

    Hermes imprime SOLO la respuesta final en stdout y suele terminar con
    codigo 0 aunque el modelo falle (errores de cuota, auth o red viajan en el
    texto de stdout). Por eso el fallo se detecta por firmas de error en la
    salida, no solo por el codigo de salida.
    """

    kind = ExecutorType.HERMES

    def __init__(self) -> None:
        settings = load_settings()
        self.executable = os.environ.get("MAOQ_HERMES_BIN") or discover_hermes_binary()
        self.model = os.environ.get("MAOQ_HERMES_MODEL") or settings.hermes_model
        self.provider = os.environ.get("MAOQ_HERMES_PROVIDER") or settings.hermes_provider

    def _build_command(self, task: Task) -> list[str]:
        command = [self.executable, "-z", task.prompt]
        if self.provider:
            command.extend(["--provider", self.provider])
        if self.model:
            command.extend(["--model", self.model])
        command.extend(["--accept-hooks", "--yolo"])
        # En Windows los .cmd/.bat no son ejecutables directos para CreateProcess;
        # se lanzan via cmd.exe. list2cmdline conserva el quoting del prompt.
        if self.executable.lower().endswith((".cmd", ".bat")):
            command = ["cmd", "/c", *command]
        return command

    def run(self, task: Task) -> TaskResult:
        started = time.monotonic()
        command = self._build_command(task)
        outcome = _run_agent_process(command, task.workspace, timeout=task.timeout_seconds)
        if outcome.not_found:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=127,
                summary=f"Ejecutable no encontrado: {self.executable}", stderr=outcome.not_found)
        if outcome.timed_out:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=124,
                summary="La tarea Hermes excedio el timeout", stderr="timeout")
        stdout = outcome.stdout
        stderr = outcome.stderr
        output = f"{stdout}\n{stderr}"
        failed = outcome.returncode != 0 or _contains_failure_signature(output)
        if not failed and not stdout.strip():
            failed = True
            summary = "Hermes devolvio una respuesta vacia"
        else:
            summary = (
                f"hermes finalizo con codigo {outcome.returncode}"
                if not failed
                else "hermes reporto un fallo (cuota/auth/modelo)"
            )
        # Native Hermes is attempted first. If its local provider is not
        # authenticated or its free route is unavailable, retry once through
        # NVIDIA NIM when a key is present. This keeps native-first behavior
        # while making the worker recoverable in unattended runs.
        if failed and not self.provider and os.environ.get("NVIDIA_API_KEY"):
            fallback = [self.executable, "-z", task.prompt,
                        "--provider", "nvidia",
                        "--model", "nvidia/nemotron-3-super-120b-a12b",
                        "--accept-hooks", "--yolo"]
            if self.executable.lower().endswith((".cmd", ".bat")):
                fallback = ["cmd", "/c", *fallback]
            retry = _run_agent_process(fallback, task.workspace,
                                       env=os.environ.copy(), timeout=task.timeout_seconds)
            retry_output = f"{retry.stdout}\n{retry.stderr}"
            if retry.returncode == 0 and retry.stdout.strip() and not _contains_failure_signature(retry_output):
                stdout, stderr, outcome = retry.stdout, retry.stderr, retry
                failed = False
                summary = "hermes finalizo mediante fallback NVIDIA"
        status = TaskStatus.FAILED if failed else TaskStatus.SUCCEEDED
        return TaskResult(
            task_id=task.id,
            status=status,
            exit_code=outcome.returncode,
            summary=summary,
            stdout=stdout[-20000:],
            stderr=stderr[-20000:],
            duration_seconds=round(time.monotonic() - started, 3),
        )


def _contains_failure_signature(output: str) -> bool:
    lowered = output.lower()
    return any(signature.lower() in lowered for signature in _HERMES_FAILURE_SIGNATURES)


def discover_hermes_binary() -> str:
    """Find Hermes CLI from PATH."""
    from shutil import which

    on_path = which("hermes")
    if on_path:
        real_executable = Path("D:/datos jt7/proyectos/hermes-agent/venv311/Scripts/hermes.exe")
        if real_executable.exists():
            return str(real_executable)
        return on_path
    # Fallback a ubicacion comun en Windows (~/.local/bin/hermes.cmd)
    local_bin = Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "hermes.cmd"
    if local_bin.exists():
        return str(local_bin)
    return "hermes"


def discover_kilo_binary() -> str:
    """Find Kilo CLI from PATH or its standard VS Code extension location."""
    from shutil import which

    on_path = which("kilo")
    if on_path:
        return on_path
    extension_root = Path(os.environ.get("USERPROFILE", "")) / ".vscode" / "extensions"
    candidates = sorted(extension_root.glob("kilocode.kilo-code-*\\bin\\kilo.exe"), reverse=True)
    return str(candidates[0]) if candidates else "kilo"


def discover_cline_binary() -> str | None:
    """Find a configured Cline CLI; VS Code extensions are not CLIs."""
    from shutil import which

    return which("cline")


def executor_for(kind: ExecutorType) -> Executor:
    return {ExecutorType.SIMULATED: SimulatedExecutor(), ExecutorType.KILO: KiloExecutor(),
            ExecutorType.CLINE: ClineExtensionExecutor(), ExecutorType.HERMES: HermesExecutor()}[kind]
