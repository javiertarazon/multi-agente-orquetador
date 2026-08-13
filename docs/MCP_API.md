# Interfaces API y MCP

## API HTTP

Instalar con `pip install -e ".[api]"` y ejecutar `scripts/run-api.ps1`.

- `GET /health`
- `GET /tasks`
- `POST /tasks` con `{ "prompt": "...", "executor": "simulated|kilo|cline" }`
- `GET /tasks/{id}`

La API escucha en `127.0.0.1:8765` por defecto.

## MCP

Instalar con `pip install -e ".[mcp]"` y ejecutar `scripts/run-mcp.ps1`. El transporte inicial es stdio, apropiado para clientes locales como Copilot/Cline/Kilo mediante su configuracion MCP.

Herramientas: `health`, `create_task`, `create_plan`, `execute_plan`, `list_tasks`, `get_task`, `review_task`, `claim_task`, `cancel_task`, `get_plan_status`, `get_artifact` y `get_notifications`.

`create_plan` no ejecuta automaticamente por defecto (`auto_execute: false`). Cada plan se guarda en una SQLite aislada y tiene un supervisor propio al ejecutarse. Las tareas sin politica explicita usan `auto_on_pass`: se aprueban solo cuando el ejecutor, las validaciones y los artefactos cumplen. Usa `manual` o `milestone` para detenerse en puntos que requieran revision humana.

El supervisor ejecuta `validation_commands`, registra intentos y detecta archivos modificados dentro de `allowed_paths`. Si una tarea falla, clasifica el error, guarda un episodio y programa el reintento con backoff exponencial. Las tareas sin heartbeat se recuperan automaticamente; al agotar los reintentos se marcan `timed_out` o `failed`.

## Confirmacion desde Copilot

Despues de presentar un plan, Copilot debe preguntar:

> ¿Quieres delegar este plan a Multi Agente Orquestado para que Kilo y Cline lo ejecuten?

Solo una respuesta afirmativa activa `create_plan`. El MCP no puede dibujar controles dentro del chat por si mismo; la pregunta la realiza Copilot siguiendo `.github/copilot-instructions.md`.

El servidor solo administra tareas; la ejecucion pasa por el worker y las politicas del orquestador.
