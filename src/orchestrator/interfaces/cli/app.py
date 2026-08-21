import os
from pathlib import Path

import typer

from orchestrator.adapters.storage import TaskStore
from orchestrator.application.worker import Worker
from orchestrator.domain.models import ExecutorType, Task

app = typer.Typer(help="Multi Agente Orquestado")
task_app = typer.Typer(help="Gestion de tareas")
plan_app = typer.Typer(help="Delegacion de planes aprobados")
agent_app = typer.Typer(help="Diagnostico y configuracion de agentes CLI")
opencode_app = typer.Typer(help="Configuracion del orquestador OpenCode")
session_app = typer.Typer(help="Sesiones reanudables")
app.add_typer(task_app, name="task")
app.add_typer(plan_app, name="plan")
app.add_typer(agent_app, name="agent")
app.add_typer(opencode_app, name="opencode")
app.add_typer(session_app, name="session")


def store() -> TaskStore:
    return TaskStore()


@app.command()
def init() -> None:
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    store()
    typer.echo("Inicializado")


@app.command()
def doctor() -> None:
    import os
    import shutil

    vscode_extensions = os.path.join(os.environ.get("USERPROFILE", ""), ".vscode", "extensions")
    kilo_extension = any(Path(vscode_extensions).glob("kilocode.kilo-code-*"))
    cline_extension = any(Path(vscode_extensions).glob("saoudrizwan.claude-dev-*"))
    checks = {
        "python": True,
        "git": bool(shutil.which("git")),
        "kilo": bool(shutil.which("kilo")) or kilo_extension,
        "cline": bool(shutil.which("cline")) or cline_extension,
    }
    for name, available in checks.items():
        typer.echo(f"{name}: {'OK' if available else 'opcional/no encontrado'}")


@task_app.command("create")
def create(
    prompt: str,
    executor: ExecutorType = ExecutorType.SIMULATED,
    priority: int = 100,
    workspace: str = ".",
) -> None:
    task = Task(prompt=prompt, executor=executor, priority=priority, workspace=workspace)
    store().add(task)
    typer.echo(task.id)


@task_app.command("list")
def list_tasks() -> None:
    for task in store().list():
        typer.echo(f"{task.id} {task.status.value} {task.executor.value} {task.prompt}")


@task_app.command("show")
def show(task_id: str) -> None:
    task = store().get(task_id)
    if not task:
        raise typer.BadParameter("Tarea no encontrada")
    typer.echo(task.model_dump_json(indent=2))
    result = store().get_result(task_id)
    if result:
        typer.echo(result.model_dump_json(indent=2))


@task_app.command("cancel")
def cancel(task_id: str) -> None:
    typer.echo("cancelled" if store().cancel(task_id) else "not found or already finished")


@task_app.command("recover")
def recover(max_age_seconds: int = 300) -> None:
    """Recupera tareas running sin heartbeat y aplica su backoff."""
    typer.echo({"recovered": store().recover_stale_running(max_age_seconds)})


@app.command()
def report() -> None:
    tasks = store().list()
    counts = {}
    for task in tasks:
        counts[task.status.value] = counts.get(task.status.value, 0) + 1
    typer.echo({"total": len(tasks), "by_status": counts})


@app.command()
def logs() -> None:
    path = Path("logs")
    for item in sorted(path.glob("*.log")):
        typer.echo(str(item))


@agent_app.command("doctor")
def agent_doctor() -> None:
    """Diagnostica binarios y credenciales de los agentes CLI disponibles."""
    import os
    import shutil

    from orchestrator.adapters.config import load_settings
    from orchestrator.adapters.executors import (
        discover_cline_binary,
        discover_hermes_binary,
        discover_kilo_binary,
    )

    settings = load_settings()
    binaries = {
        "kilo": discover_kilo_binary(),
        "cline": discover_cline_binary() or "no encontrado",
        "hermes": discover_hermes_binary(),
        "opencode": shutil.which("opencode") or "no encontrado",
    }
    for name, binary in binaries.items():
        typer.echo(f"{name}: {binary}")

    typer.echo("modelos (config/default.yaml):")
    typer.echo(f"kilo: {settings.kilo_model}")
    typer.echo(f"hermes: {settings.hermes_provider}/{settings.hermes_model}")
    typer.echo(f"cline: {settings.cline_provider}/{settings.cline_model}")

    typer.echo("credenciales:")
    creds = {
        "GOOGLE_GENERATIVE_AI_API_KEY": "configurada" if os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY") else "no configurada",
        "MAOQ_HERMES_BIN": os.environ.get("MAOQ_HERMES_BIN"),
        "MAOQ_HERMES_MODEL": os.environ.get("MAOQ_HERMES_MODEL"),
        "MAOQ_HERMES_PROVIDER": os.environ.get("MAOQ_HERMES_PROVIDER"),
        "HF_TOKEN": "configurada" if os.environ.get("HF_TOKEN") else "no configurada",
        "NVIDIA_API_KEY": "configurada" if os.environ.get("NVIDIA_API_KEY") else "no configurada",
    }
    for name, value in creds.items():
        typer.echo(f"{name}: {value}")

    if os.environ.get("MAOQ_HERMES_PROVIDER") and not os.environ.get("MAOQ_HERMES_MODEL"):
        typer.echo("Aviso: MAOQ_HERMES_PROVIDER esta definido pero falta MAOQ_HERMES_MODEL")


@agent_app.command("list")
def agent_list() -> None:
    """Lista los agentes CLI conocidos y si estan disponibles."""
    import shutil

    for name in ("kilo", "cline", "hermes", "opencode"):
        typer.echo(f"{name}: {shutil.which(name) or 'usar MAOQ_*_BIN o extension VS Code'}")


@plan_app.command("delegate")
def delegate(plan_file: Path) -> None:
    """Muestra el comando de delegacion para un plan JSON aprobado."""
    if not plan_file.exists():
        raise typer.BadParameter("No existe el archivo del plan")
    typer.echo(f"Plan listo para delegar: {plan_file}")
    typer.echo("Usa Copilot y responde 'Si' a la pregunta de delegacion para activar el MCP.")


@plan_app.command("status")
def plan_status(plan_id: str) -> None:
    database = Path("data") / "plans" / f"{plan_id}.db"
    plan_store = TaskStore(str(database))
    counts: dict[str, int] = {}
    for task in plan_store.list(limit=1000):
        counts[task.status.value] = counts.get(task.status.value, 0) + 1
    typer.echo(
        {
            "plan_id": plan_id,
            "by_status": counts,
            "goals": [goal.model_dump(mode="json") for goal in plan_store.goals(plan_id)],
        }
    )


@session_app.command("resume")
def session_resume(plan_id: str) -> None:
    """Reanuda un plan persistido donde se quedo (reencola pendientes y supervisor)."""
    from orchestrator.interfaces.mcp.server import resume_plan

    typer.echo(resume_plan(plan_id))


@session_app.command("summary")
def session_summary(plan_id: str, limit: int = 5) -> None:
    """Muestra el resumen compacto de una sesion persistida."""
    from orchestrator.interfaces.mcp.server import session_summary

    typer.echo(session_summary(plan_id, limit=limit))


@app.command()
def worker(once: bool = typer.Option(False, "--once")) -> None:
    if not once:
        typer.echo("MVP: usa --once para procesar una tarea")
        raise typer.Exit(2)
    raise typer.Exit(Worker(store()).run_once())


@app.command("run-until-terminal")
def run_until_terminal(
    max_cycles: int = typer.Option(100, min=1, max=10000),
    idle_cycles: int = typer.Option(2, min=1, max=100),
) -> None:
    """Procesa tareas automáticamente hasta terminar o alcanzar un límite."""
    task_store = store()
    task_worker = Worker(task_store)
    idle = 0
    for _ in range(max_cycles):
        code = task_worker.run_once()
        active = [
            task
            for task in task_store.list(limit=1000)
            if task.status.value in {"queued", "running", "retry_wait"}
        ]
        if not active:
            typer.echo("Plan terminado: no quedan tareas ejecutables")
            return
        # Un ciclo sin tareas ejecutables puede significar backoff o revisión;
        # no se mantiene un busy-loop infinito en ese estado.
        idle = (
            idle + 1
            if code == 0 and not any(task.status.value == "queued" for task in active)
            else 0
        )
        if idle >= idle_cycles:
            typer.echo("Ejecución pausada: no hay tareas listas; revise backoff o aprobación")
            return
    typer.echo(f"Límite alcanzado: {max_cycles} ciclos")


@opencode_app.command("setup")
def opencode_setup(
    venv: str = typer.Option(".venv", help="Ruta al entorno virtual"),
    force: bool = typer.Option(False, "--force", help="Sobrescribe archivos existentes"),
) -> None:
    """Genera opencode.json con el MCP local y el agente orquestador."""
    import json

    project_root = Path.cwd()
    venv_path = Path(venv)
    python = (
        venv_path / "Scripts" / "python.exe" if os.name == "nt" else venv_path / "bin" / "python"
    )
    if not python.exists():
        raise typer.BadParameter(f"No existe el interprete {python}")

    config_path = project_root / "opencode.json"
    if config_path.exists() and not force:
        raise typer.BadParameter("opencode.json ya existe; usa --force para sobrescribirlo")
    config = {
        "$schema": "https://opencode.ai/config.json",
        "mcp": {
            "multi-agente-orquestado": {
                "type": "local",
                "command": [python.as_posix(), "-m", "orchestrator.interfaces.mcp.server"],
                "cwd": ".",
                "environment": {"PYTHONPATH": "src"},
                "enabled": True,
                "timeout": 15000,
            }
        },
    }
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    typer.echo(f"Generado {config_path}")

    agent_dir = project_root / ".opencode" / "agents"
    agent_path = agent_dir / "orchestrator.md"
    if agent_path.exists() and not force:
        raise typer.BadParameter(f"{agent_path} ya existe; usa --force para sobrescribirlo")
    agent_dir.mkdir(parents=True, exist_ok=True)
    agent_path.write_text(ORCHESTRATOR_AGENT, encoding="utf-8")
    typer.echo(f"Generado {agent_path}")
    typer.echo("Recarga OpenCode y verifica con: opencode mcp list y opencode agent list")


@opencode_app.command("doctor")
def opencode_doctor() -> None:
    """Comprueba que OpenCode ve el MCP local y el agente orquestador."""
    import shutil
    import subprocess

    if not shutil.which("opencode"):
        typer.echo("opencode: no encontrado")
        raise typer.Exit(2)

    def _run(args: list[str]) -> tuple[int, str]:
        try:
            completed = subprocess.run(
                ["cmd", "/c", *args], capture_output=True, text=True, check=False, timeout=60
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return 1, str(error)
        return completed.returncode, (completed.stdout or "") + (completed.stderr or "")

    _, mcp_output = _run(["opencode", "mcp", "list"])
    _, agent_output = _run(["opencode", "agent", "list"])
    typer.echo(
        "MCP multi-agente-orquestado: "
        + ("OK" if "multi-agente-orquestado" in mcp_output else "no conectado")
    )
    typer.echo(
        "Agente orchestrator: " + ("OK" if "orchestrator" in agent_output else "no encontrado")
    )


ORCHESTRATOR_AGENT = """---
description: Orquestador multi-agente: planifica, delega y supervisa planes en el orquestador "multi agente orquestado" via MCP.
mode: primary
temperature: 0.2
permission:
  read: allow
  edit: allow
  bash: allow
  multi-agente-orquestado_*: allow
  webfetch: deny
  websearch: deny
---

# Orquestador multi-agente

Eres el **orquestador principal**. Recibes un objetivo de alto nivel y lo
descompones en tareas ejecutables que delega a agentes worker (Kilo, Cline o
Hermes) a traves del servidor MCP `multi-agente-orquestado`. Tu trabajo es
planificar, delegar, supervisar y reportar; NO ejecutas el trabajo de los
workers tu mismo.

## Herramientas disponibles (prefijo multi-agente-orquestado_)

- `health`: comprobar que el servidor MCP responde.
- `create_plan`: importa un plan y crea sus tareas ordenadas con dependencias,
  executors, validaciones, timeout y politica de aprobacion.
- `execute_plan`: inicia la ejecucion de un plan ya creado.
- `get_plan_status`: resume progreso de un plan (total, by_status, goals).
- `get_episodes`: memoria persistente de fallos/correcciones previos (compact).
- `get_task`: detalle de una tarea y su resultado.
- `list_tasks`: lista tareas del store global (offset/limit/compact).
- `review_task`: aprueba o rechaza una tarea que requiere revision.
- `cancel_task`: cancela una tarea pendiente o en ejecucion.
- `get_artifact`: artefactos producidos por una tarea (compact para listar).
- `get_notifications`: avisos de inicio, evaluacion, reintento y finalizacion.
- `claim_task`: (solo workers) reclama la siguiente tarea.

## Flujo obligatorio

1. **Interpretar el objetivo.** Si falta contexto o workspace, pide aclaracion
   antes de crear el plan.
2. **Comprobar el servidor.** Llama a `health` primero; si falla, detente y
   reporta como bloquear el MCP server (`.venv\\Scripts\\python.exe -m
   orchestrator.interfaces.mcp.server`).
3. **Crear el plan** con `create_plan`. Antes, consulta `get_episodes(compact=true)`
   para revisar fallos previos del mismo workspace y evitar repetirlos (ahorro de
   tokens). Descompone en pasos secuenciales con
   `depends_on` cuando haya dependencias reales. Para cada tarea define:
   - `prompt`: instruccion concreta y autocontenida (el worker trabaja en el
     workspace; no asumas que conoce el plan completo).
   - `executor`: orden de preferencia `kilo`, `hermes`, `cline`; usa `simulated`
     solo para tareas de coordinacion o pruebas.
   - `validation_commands`: comandos de verificacion que el worker debe poder
     cumplir (p.ej. tests o checks sintacticos).
   - `timeout_seconds`: acotado por tarea; 900 por defecto.
   - `max_retries`: 1 o 2 para tareas de codigo; 0 para tareas simples.
   - `requires_review`: true para hitos o cambios sensibles, false para el resto.
   - `approval_policy`: `auto_on_pass` por defecto.
   - `dry_run`: true si el usuario solo quiere el plan sin ejecutar.
4. **Confirmar con el usuario.** Si `auto_execute` es false (por defecto),
   muestra el plan (objetivo, tareas, executors, dependencias) y pregunta:
   `El plan esta listo. ¿Quieres ejecutarlo con multi agente orquestado?`
   Solo con respuesta afirmativa llama a `execute_plan`.
5. **Supervisar.** Con `get_plan_status` cada pocos segundos hasta que todas las
   tareas esten en `succeeded`, `failed`, `rejected` o `cancelled`. Si una tarea
   esta en `awaiting_approval` o `retry_wait`, revisa su resultado con `get_task`
   y decide:
   - Si el resultado es correcto, llama a `review_task(approved=true)`.
   - Si el resultado es incorrecto, llama a `review_task(approved=false)` con
     `feedback` concreto y accionable.
   - Usa `get_episodes` para evaluar con contexto de intentos previos sin
     reenviar sus salidas completas.
6. **Reintentos.** Si una tarea fallo y tiene `max_retries` restantes, el
   supervisor del orquestador reintenta automaticamente; tu solo revisa el
   resultado final. Si fallo tras agotar reintentos, valora si el plan debe
   abortarse o si una tarea corregida en el workspace permite reejecutar.
7. **Reportar.** Al terminar, resume: objetivo, tareas por estado, artefactos
   relevantes (usa `get_artifact`), fallos y proximo paso. No pegues salida
   bruta de workers; usa resumenes y artefactos.

## Reglas

- Responde en espanol.
- El workspace objetivo es el del plan; no asumas que es el directorio actual
  del agente. Usa rutas relativas al workspace salvo indicacion contraria.
- No edites codigo tu mismo si el objetivo es delegable; tu rol es orquestar.
  Si algo no es delegable (decision, diseno), hazlo con la minima edicion y
  documentalo en el reporte.
- No uses `websearch` ni `webfetch` salvo instruccion explicita.
- Conserva el contexto: envia solo objetivo, restricciones y contexto minimo a
  los workers.
"""


if __name__ == "__main__":
    app()
