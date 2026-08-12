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

Herramientas: `health`, `create_task`, `create_plan`, `list_tasks`, `get_task`, `claim_task`, `cancel_task`, `get_artifact` y `get_notifications`.

`create_plan` ejecuta automaticamente el plan en segundo plano por defecto. Cada tarea se asigna al ejecutor indicado (`kilo`, `cline` o `simulated`) y las dependencias se respetan. Para importar sin ejecutar, usa `auto_execute: false` y luego `maoq worker --once`.

El supervisor ejecuta `validation_commands` al terminar cada agente. Si fallan, la tarea se marca como incumplida, se notifica y se reencola hasta `max_retries`; al agotar los reintentos queda `failed` para revision humana.

## Confirmacion desde Copilot

Despues de presentar un plan, Copilot debe preguntar:

> ¿Quieres delegar este plan a Multi Agente Orquestado para que Kilo y Cline lo ejecuten?

Solo una respuesta afirmativa activa `create_plan`. El MCP no puede dibujar controles dentro del chat por si mismo; la pregunta la realiza Copilot siguiendo `.github/copilot-instructions.md`.

El servidor solo administra tareas; la ejecucion pasa por el worker y las politicas del orquestador.
