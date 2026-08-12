from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
import os

from orchestrator.domain.models import ExecutorType, Task, TaskResult, TaskStatus


class Executor(ABC):
    kind: ExecutorType

    @abstractmethod
    def run(self, task: Task) -> TaskResult:
        raise NotImplementedError


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
        try:
            completed = subprocess.run(command, cwd=task.workspace, text=True,
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=task.timeout_seconds, check=False)
            status = TaskStatus.SUCCEEDED if completed.returncode == 0 else TaskStatus.FAILED
            return TaskResult(task_id=task.id, status=status, exit_code=completed.returncode,
                summary=f"{self.kind.value} finalizo con codigo {completed.returncode}",
                stdout=(completed.stdout or "")[-20000:], stderr=(completed.stderr or "")[-20000:],
                duration_seconds=round(time.monotonic() - started, 3))
        except FileNotFoundError as error:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=127,
                summary=f"Ejecutable no encontrado: {self.command[0]}", stderr=str(error))
        except subprocess.TimeoutExpired as error:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=124,
                summary="La tarea excedio el timeout", stderr=str(error))


class KiloExecutor(SubprocessExecutor):
    def __init__(self) -> None:
        executable = os.environ.get("MAOQ_KILO_BIN") or discover_kilo_binary()
        auto_flag = ["--auto"]
        model = os.environ.get("MAOQ_KILO_MODEL", "kilo/cohere/north-mini-code:free")
        if model:
            auto_flag.extend(["--model", model])
        super().__init__([executable, "run"], ExecutorType.KILO, auto_flag)


class ClineExecutor(SubprocessExecutor):
    def __init__(self) -> None:
        executable = os.environ.get("MAOQ_CLINE_BIN") or discover_cline_binary()
        if executable:
            super().__init__([executable, "--json"], ExecutorType.CLINE,
                             ["--auto-approve", "true"])
        else:
            super().__init__(["cline"], ExecutorType.CLINE, [])

    def run(self, task: Task) -> TaskResult:
        if not self.command[0] or self.command[0] == "cline":
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                exit_code=127,
                summary="Cline esta instalado como extension, pero no tiene CLI/ACP configurado",
                stderr="Configura MAOQ_CLINE_BIN o MAOQ_CLINE_BRIDGE para un bridge headless.",
            )
        started = time.monotonic()
        command = [*self.command, *self.auto_flag, "--cwd", task.workspace, task.prompt]
        try:
            completed = subprocess.run(command, cwd=task.workspace, text=True,
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=task.timeout_seconds, check=False)
            status = TaskStatus.SUCCEEDED if completed.returncode == 0 else TaskStatus.FAILED
            return TaskResult(task_id=task.id, status=status, exit_code=completed.returncode,
                summary=f"cline finalizo con codigo {completed.returncode}",
                stdout=(completed.stdout or "")[-20000:], stderr=(completed.stderr or "")[-20000:],
                duration_seconds=round(time.monotonic() - started, 3))
        except FileNotFoundError as error:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=127,
                summary=f"Ejecutable no encontrado: {self.command[0]}", stderr=str(error))
        except subprocess.TimeoutExpired as error:
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, exit_code=124,
                summary="La tarea Cline excedio el timeout", stderr=str(error))


class ClineExtensionExecutor(ClineExecutor):
    """Ejecuta Cline mediante un bridge externo de la extension o ACP.

    El bridge recibe el prompt como ultimo argumento y debe devolver codigo cero
    cuando termina correctamente. La extension de VS Code no expone este bridge
    por defecto; se configura con MAOQ_CLINE_BRIDGE.
    """

    def __init__(self) -> None:
        bridge = os.environ.get("MAOQ_CLINE_BRIDGE")
        if bridge:
            self.command = [bridge]
            self.kind = ExecutorType.CLINE
            self.auto_flag = []
        else:
            super().__init__()


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
            ExecutorType.CLINE: ClineExtensionExecutor()}[kind]
