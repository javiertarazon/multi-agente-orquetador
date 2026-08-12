from orchestrator.adapters.storage import TaskStore
from orchestrator.domain.models import ExecutorType, Task

try:
    from fastapi import FastAPI, HTTPException
except ImportError as error:
    raise RuntimeError("Instala el extra [api] para usar la API HTTP") from error

app = FastAPI(title="Multi Agente Orquestado", version="0.1.0")
store = TaskStore()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks() -> list[dict]:
    return [task.model_dump(mode="json") for task in store.list()]


@app.post("/tasks", status_code=201)
def create_task(payload: dict) -> dict:
    try:
        task = Task(prompt=str(payload["prompt"]),
                    executor=ExecutorType(payload.get("executor", "simulated")),
                    workspace=str(payload.get("workspace", ".")))
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    store.add(task)
    return task.model_dump(mode="json")


@app.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    task = store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    result = store.get_result(task_id)
    return {"task": task.model_dump(mode="json"),
            "result": result.model_dump(mode="json") if result else None}


@app.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str) -> dict[str, bool]:
    return {"cancelled": store.cancel(task_id)}


@app.get("/tasks/{task_id}/artifacts")
def artifacts(task_id: str) -> list[dict]:
    return [item.model_dump(mode="json") for item in store.artifacts(task_id)]
