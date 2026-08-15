from pathlib import Path

import typer

from orchestrator.adapters.storage import TaskStore
from orchestrator.application.worker import Worker
from orchestrator.domain.models import ExecutorType, Task

app = typer.Typer(help="Multi Agente Orquestado")
task_app = typer.Typer(help="Gestion de tareas")
plan_app = typer.Typer(help="Delegacion de planes aprobados")
app.add_typer(task_app, name="task")
app.add_typer(plan_app, name="plan")


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
    checks = {"python": True, "git": bool(shutil.which("git")),
              "kilo": bool(shutil.which("kilo")) or kilo_extension,
              "cline": bool(shutil.which("cline")) or cline_extension}
    for name, available in checks.items():
        typer.echo(f"{name}: {'OK' if available else 'opcional/no encontrado'}")


@task_app.command("create")
def create(prompt: str, executor: ExecutorType = ExecutorType.SIMULATED,
           priority: int = 100, workspace: str = ".") -> None:
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


@app.command()
def agent() -> None:
    import shutil
    for name in ("kilo", "cline"):
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
    typer.echo({"plan_id": plan_id, "by_status": counts, "goals": [goal.model_dump(mode="json") for goal in plan_store.goals(plan_id)]})


@app.command()
def worker(once: bool = typer.Option(False, "--once")) -> None:
    if not once:
        typer.echo("MVP: usa --once para procesar una tarea")
        raise typer.Exit(2)
    raise typer.Exit(Worker(store()).run_once())


@app.command("run-until-terminal")
def run_until_terminal(max_cycles: int = typer.Option(100, min=1, max=10000),
                       idle_cycles: int = typer.Option(2, min=1, max=100)) -> None:
    """Procesa tareas automáticamente hasta terminar o alcanzar un límite."""
    task_store = store()
    task_worker = Worker(task_store)
    idle = 0
    for _ in range(max_cycles):
        code = task_worker.run_once()
        active = [task for task in task_store.list(limit=1000)
                  if task.status.value in {"queued", "running", "retry_wait"}]
        if not active:
            typer.echo("Plan terminado: no quedan tareas ejecutables")
            return
        # Un ciclo sin tareas ejecutables puede significar backoff o revisión;
        # no se mantiene un busy-loop infinito en ese estado.
        idle = idle + 1 if code == 0 and not any(
            task.status.value == "queued" for task in active
        ) else 0
        if idle >= idle_cycles:
            typer.echo("Ejecución pausada: no hay tareas listas; revise backoff o aprobación")
            return
    typer.echo(f"Límite alcanzado: {max_cycles} ciclos")


if __name__ == "__main__":
    app()
