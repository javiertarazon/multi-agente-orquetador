import os
import threading
import time
from pathlib import Path
from uuid import uuid4

from orchestrator.adapters.storage import TaskStore
from orchestrator.application.goal_engine import GoalEngine
from orchestrator.application.learning_engine import LearningEngine
from orchestrator.application.worker import Worker
from orchestrator.domain.models import ExecutorType, Task

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as error:
    raise RuntimeError("Instala el extra [mcp] para usar el servidor MCP") from error

mcp = FastMCP("multi-agente-orquestado")
store = TaskStore()
_supervisor_lock = threading.Lock()
_supervisor_threads: dict[str, threading.Thread] = {}
_plan_stores: dict[str, TaskStore] = {}


def _isolated_store(plan_id: str) -> TaskStore:
    """Return the SQLite store dedicated to one plan."""
    if plan_id not in _plan_stores:
        database = Path("data") / "plans" / f"{plan_id}.db"
        _plan_stores[plan_id] = TaskStore(str(database))
    return _plan_stores[plan_id]


def _store_for_task(task_id: str) -> TaskStore:
    if store.get(task_id):
        return store
    for plan_store in _plan_stores.values():
        if plan_store.get(task_id):
            return plan_store
    for database in Path("data/plans").glob("*.db"):
        candidate = TaskStore(str(database))
        if candidate.get(task_id):
            _plan_stores[database.stem] = candidate
            return candidate
    return store


@mcp.tool()
def health() -> dict[str, str]:
    """Comprueba el estado del orquestador."""
    return {"status": "ok"}


@mcp.tool()
def create_task(prompt: str, executor: str = "simulated", workspace: str = ".") -> dict:
    """Crea una tarea compacta para el worker."""
    task = Task(prompt=prompt, executor=ExecutorType(executor), workspace=workspace)
    store.add(task)
    return {"id": task.id, "status": task.status.value, "executor": task.executor.value}


@mcp.tool()
def create_plan(plan: str, tasks: list[dict], workspace: str = ".", auto_execute: bool = False,
                target_return: float | None = None, max_drawdown: float | None = None,
                max_iterations: int = 3, lessons_from: str | None = None) -> dict:
    """Importa un plan aprobado por Copilot y crea sus tareas ordenadas.

    Cada elemento puede incluir prompt, executor, priority, depends_on (indices
    de tareas anteriores), allowed_paths, validation_commands y max_retries.
    Si `lessons_from` apunta a un plan_id anterior, sus lecciones aprendidas se
    prependen al objetivo como bloque `LECCIONES PREVIAS`.
    """
    if not plan.strip() or not tasks:
        return {"error": "plan y tasks son obligatorios"}
    if os.environ.get("MAOQ_REQUIRE_REAL_EXECUTORS") == "1":
        simulated = [index for index, item in enumerate(tasks)
                     if item.get("executor", "simulated") == "simulated"
                     and not any(str(tag).lower() in {"smoke", "smoke_test", "coordination"}
                                 for tag in item.get("tags", []))]
        if simulated:
            return {"error": "OpenCode debe delegar en Kilo, Cline o Hermes; "
                    f"tareas simulated rechazadas: {simulated}"}
    if lessons_from:
        lecciones = LearningEngine(_isolated_store(lessons_from)).lessons(lessons_from)
        if lecciones:
            bloque = "LECCIONES PREVIAS\n" + "\n".join(f"- {item}" for item in lecciones)
            plan = f"{bloque}\n\n{plan}"
    plan_id = uuid4().hex
    plan_store = _isolated_store(plan_id)
    goal = GoalEngine(plan_store).create_root(plan_id, plan, [])
    created: list[Task] = []
    for index, item in enumerate(tasks):
        depends_on = item.get("depends_on", [])
        dependency_ids = [created[int(value)].id for value in depends_on]
        task = Task(
            prompt=str(item["prompt"]),
            executor=ExecutorType(item.get("executor", "simulated")),
            priority=int(item.get("priority", index + 1)),
            workspace=str(item.get("workspace", workspace)),
            allowed_paths=list(item.get("allowed_paths", [])),
            validation_commands=list(item.get("validation_commands", [])),
            depends_on=dependency_ids,
            max_retries=int(item.get("max_retries", 0)),
            retry_count=0,
            timeout_seconds=max(1, int(item.get("timeout_seconds", 900))),
            dry_run=bool(item.get("dry_run", False)),
            approval_policy=item.get("approval_policy", "auto_on_pass"),
            requires_review=bool(item.get("requires_review", True)),
            reviewer=str(item.get("reviewer", "copilot")),
            plan_id=plan_id,
            model=item.get("model"),
            backoff_base=float(item.get("backoff_base", 2.0)),
            goal_id=goal.id,
            tags=list(item.get("tags", [])),
            metadata={"plan": plan, "plan_index": index,
                      "role": str(item.get("role", "executor")),
                      "plan_id": plan_id, "target_return": target_return,
                      "max_drawdown": max_drawdown, "max_iterations": max_iterations,
                      "iteration": 0},
        )
        plan_store.add(task)
        GoalEngine(plan_store).attach_task(goal.id, task.id)
        created.append(task)
    if auto_execute:
        _start_supervisor([task.id for task in created], plan_store)
    return {"plan": plan, "task_ids": [task.id for task in created],
            "plan_id": plan_id, "database": str(plan_store.database),
            "auto_execute": auto_execute,
            "tasks": [{"id": task.id, "executor": task.executor.value,
                       "depends_on": task.depends_on} for task in created]}


@mcp.tool()
def execute_plan(plan_task_ids: list[str], approved_by: str = "copilot") -> dict:
    """Inicia un plan despues de la confirmacion explicita del usuario.

    Copilot debe preguntar antes al usuario y pasar los IDs devueltos por
    create_plan. La ejecucion se detiene en cada tarea que requiere revision.
    """
    if not plan_task_ids:
        return {"error": "plan_task_ids es obligatorio"}
    plan_store = _store_for_task(plan_task_ids[0])
    tasks = [plan_store.get(task_id) for task_id in plan_task_ids]
    missing = [task_id for task_id, task in zip(plan_task_ids, tasks) if task is None]
    if missing:
        return {"error": "tareas no encontradas", "task_ids": missing}
    _start_supervisor(plan_task_ids, plan_store)
    return {"started": True, "approved_by": approved_by, "task_ids": plan_task_ids,
            "message": "Plan iniciado; revisar resultados con get_task y get_artifact"}


def _start_supervisor(task_ids: list[str], plan_store: TaskStore) -> None:
    """Mantiene un supervisor por proceso MCP para el plan solicitado."""
    plan_id = str(plan_store.get(task_ids[0]).plan_id or plan_store.get(task_ids[0]).metadata.get("plan_id", "global"))
    with _supervisor_lock:
        existing = _supervisor_threads.get(plan_id)
        if existing and existing.is_alive():
            return
        thread = threading.Thread(
            target=_run_plan, args=(list(task_ids), plan_store), name=f"maoq-supervisor-{plan_id}", daemon=True
        )
        _supervisor_threads[plan_id] = thread
        thread.start()


def _run_plan(task_ids: list[str], plan_store: TaskStore) -> None:
    """Supervisa dependencias, ejecuciones y revisiones hasta cerrar el plan.

    Ejecuta las tareas en paralelo con el maximo de workers permitido por la
    configuracion (MAOQ_MAX_WORKERS). Las tareas con dependencias pendientes
    no salen de la cola, por lo que el paralelismo nunca salta la
    secuencialidad estrictamente necesaria.
    """
    max_workers = max(1, int(os.environ.get("MAOQ_MAX_WORKERS", "2")))
    worker = Worker(plan_store)
    while True:
        tasks = [plan_store.get(task_id) for task_id in task_ids]
        if all(task and task.status.value in {"succeeded", "failed", "timed_out", "rejected", "cancelled"} for task in tasks):
            return
        try:
            worker.run_parallel(max_workers=max_workers)
        except RuntimeError as error:
            # El proceso puede estar cerrándose mientras el supervisor daemon
            # intenta crear su pool; no debe emitir una excepción no controlada.
            if "interpreter shutdown" in str(error).lower():
                return
            raise
        except KeyError:
            # Un workspace/SQLite temporal puede desaparecer mientras termina
            # una prueba o se cierra el cliente MCP; el daemon debe salir sin
            # propagar una excepción al proceso anfitrión.
            return
        plan_id = tasks[0].plan_id if tasks and tasks[0] else None
        if plan_id:
            GoalEngine(plan_store).refresh(plan_id)
        time.sleep(0.5)


@mcp.tool()
def list_tasks(offset: int = 0, limit: int = 50, compact: bool = False) -> list[dict]:
    """Lists tasks with pagination and optional compact response.
    
    Returns only essential fields (id, status, executor) when compact is True,
    includes truncated prompt when compact is False.
    """
    offset = max(0, offset) if offset is not None else 0
    limit = max(1, min(limit or 50, 1000)) if limit is not None else 50
    return store.list_with_summary(offset=offset, limit=limit, compact=compact)


@mcp.tool()
def get_task(task_id: str, compact: bool = False) -> dict:
    """Devuelve una tarea y su resumen de ejecucion."""
    task_store = _store_for_task(task_id)
    task = task_store.get(task_id)
    if not task:
        return {"error": "task not found", "task_id": task_id}
    result = task_store.get_result(task_id)
    if compact:
        return {"task": {"id": task.id, "status": task.status.value, "executor": task.executor.value,
                    "prompt": task.prompt[:200] + ("..." if len(task.prompt) > 200 else "")},
                "result": {
                    "status": result.status.value if result else None,
                    "summary": result.summary[:200] + ("..." if len(result.summary) > 200 else "") if result else None,
                    "duration_seconds": result.duration_seconds
                } if result else None
        }
    return {"task": task.model_dump(mode="json"),
            "result": result.model_dump(mode="json") if result else None}


@mcp.tool()
def review_task(task_id: str, approved: bool, reviewer: str = "copilot",
                feedback: str = "") -> dict:
    """Aprueba o rechaza una tarea ejecutada antes de liberar sus dependencias."""
    try:
        task = _store_for_task(task_id).review(task_id, approved=approved, reviewer=reviewer, feedback=feedback)
    except (KeyError, ValueError) as error:
        return {"error": str(error), "task_id": task_id}
    return {"id": task.id, "status": task.status.value,
            "review_status": task.review_status, "reviewer": task.reviewer}


@mcp.tool()
def cancel_task(task_id: str) -> dict[str, bool]:
    """Cancela una tarea pendiente o en ejecucion."""
    return {"cancelled": _store_for_task(task_id).cancel(task_id)}


@mcp.tool()
def session_summary(plan_id: str, limit: int = 5) -> dict:
    """Resumen JSON compacto de un plan persistido para reanudar con minimo contexto.

    Devuelve total por estado, tareas pendientes (id, executor y prompt truncado
    a 120 caracteres) y las ultimas lecciones aprendidas de los episodios.
    """
    plan_store = _isolated_store(plan_id)
    tasks = plan_store.list(limit=1000)
    counts: dict[str, int] = {}
    pendientes: list[dict] = []
    terminal = {"succeeded", "failed", "timed_out", "rejected", "cancelled"}
    for task in tasks:
        counts[task.status.value] = counts.get(task.status.value, 0) + 1
        if task.status.value not in terminal:
            pendientes.append({"id": task.id, "executor": task.executor.value,
                               "prompt": task.prompt[:120] + ("..." if len(task.prompt) > 120 else "")})
    episodios = plan_store.episodes(plan_id=plan_id, limit=max(1, min(limit, 200)))
    lecciones = [f"[{ep.error_category}] {(ep.error_message or '')[:120]}" for ep in episodios]
    return {"plan_id": plan_id, "database": str(plan_store.database),
            "total": len(tasks), "by_status": counts,
            "pendientes": pendientes, "lecciones": lecciones}


@mcp.tool()
def resume_plan(plan_id: str) -> dict:
    """Reencola las tareas no terminales de un plan persistido y reanuda su supervisor.

    Util para retomar un plan tras el cierre del proceso MCP o tras fallos del
    worker, sin perder el estado ya alcanzado.
    """
    plan_store = _isolated_store(plan_id)
    terminal = {"succeeded", "failed", "timed_out", "rejected", "cancelled"}
    pendientes = [task for task in plan_store.list(limit=1000) if task.status.value not in terminal]
    for task in pendientes:
        plan_store.requeue(task)
    if pendientes:
        _start_supervisor([task.id for task in pendientes], plan_store)
    return {"plan_id": plan_id, "reencoladas": len(pendientes),
            "task_ids": [task.id for task in pendientes],
            "supervisor_alive": bool(_supervisor_threads.get(plan_id) and _supervisor_threads[plan_id].is_alive())}


@mcp.tool()
def get_plan_status(plan_id: str) -> dict:
    """Resume el progreso de un plan aislado y sus criterios de aceptación."""
    plan_store = _isolated_store(plan_id)
    tasks = plan_store.list(limit=1000)
    counts: dict[str, int] = {}
    for task in tasks:
        counts[task.status.value] = counts.get(task.status.value, 0) + 1
    metadata = tasks[0].metadata if tasks else {}
    return {"plan_id": plan_id, "database": str(plan_store.database),
            "total": len(tasks), "by_status": counts,
            "target_return": metadata.get("target_return"),
            "max_drawdown": metadata.get("max_drawdown"),
            "max_iterations": metadata.get("max_iterations"),
            "iteration": metadata.get("iteration", 0),
            "supervisor_alive": bool(_supervisor_threads.get(plan_id) and _supervisor_threads[plan_id].is_alive()),
            "goals": [goal.model_dump(mode="json") for goal in plan_store.goals(plan_id)]}


@mcp.tool()
def get_episodes(plan_id: str | None = None, limit: int = 50, compact: bool = False) -> list[dict]:
    """Memoria persistente: episodios de fallos, correcciones y metricas.

    Permite al orquestador evitar repetir errores previos sin reenviar todo el
    contexto de los intentos anteriores (ahorro de tokens).
    """
    task_store = _isolated_store(plan_id) if plan_id else store
    episodes = task_store.episodes(plan_id=plan_id, limit=limit)
    if compact:
        return [{"id": episode.id, "plan_id": episode.plan_id, "task_id": episode.task_id,
                 "error_category": episode.error_category,
                 "error_message": episode.error_message[:200]} for episode in episodes]
    return [episode.model_dump(mode="json") for episode in episodes]


@mcp.tool()
def get_artifact(task_id: str, offset: int = 0, limit: int = 50, compact: bool = False) -> list[dict]:
    """Obtiene artefactos con paginacion y respuesta compacta opcional."""
    offset = max(0, offset) if offset is not None else 0
    limit = max(1, min(limit or 50, 1000)) if limit is not None else 50
    return _store_for_task(task_id).artifacts_with_summary(task_id, offset=offset, limit=limit, compact=compact)


@mcp.tool()
def get_notifications(task_id: str | None = None, limit: int = 50) -> list[dict]:
    """Obtiene avisos compactos de inicio, evaluacion, reintento y finalizacion."""
    task_store = _store_for_task(task_id) if task_id else store
    return [notification.model_dump(mode="json") for notification in task_store.notifications(task_id, limit)]


@mcp.tool()
def claim_task() -> dict:
    """Reclama atomicamente la siguiente tarea para un worker."""
    task = store.claim_next()
    return task.model_dump(mode="json") if task else {"task": None}


if __name__ == "__main__":
    mcp.run()
