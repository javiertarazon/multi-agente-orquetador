# Cambios documentados: Autonomia v2

Fecha: 2026-08-13

## Correcciones

- Las tareas `running` antiguas se recuperan cuando el worker desaparece o pierde heartbeat.
- Los reintentos conservan su contador y usan estado `retry_wait` con backoff exponencial.
- Las tareas que agotan el tiempo terminan como `timed_out`.
- `create_plan` propaga timeout, reintentos, modelo, politica de aprobacion, backoff, tags y objetivo.
- `updated_at` se actualiza al reclamar, reencolar, recuperar y finalizar una tarea.
- Kilo y Cline se ejecutan con grupo de procesos en Windows para limitar procesos huerfanos.
- Una aprobacion de Copilot finaliza la tarea aprobada; no la vuelve a ejecutar.
- La documentacion de `auto_execute` coincide con el valor seguro `false`.

## Nuevas funciones

### Modelos

[models.py](../src/orchestrator/domain/models.py) incorpora:

- Estados `blocked`, `retry_wait`, `timed_out` y `rejected`.
- Politicas `auto_on_pass`, `manual` y `milestone`.
- Datos de plan, modelo, backoff, agenda, objetivo y tags.
- Resultado con intento, puntuacion automatica y metricas financieras.
- Modelos `Episode` y `Goal`.

### Persistencia

[storage.py](../src/orchestrator/adapters/storage.py) añade tablas auxiliares compatibles con SQLite existente:

- `task_attempts`: historial de cada ejecucion.
- `episodes`: memoria de fallos y correcciones.
- `goals`: objetivos y progreso.

Tambien añade promocion de reintentos vencidos, heartbeat de intentos, busqueda de episodios y actualizacion de objetivos.

### Worker autonomo

[worker.py](../src/orchestrator/application/worker.py) ahora:

1. Reclama una tarea.
2. Crea un intento persistido.
3. Captura baseline de archivos.
4. Ejecuta el agente y las validaciones.
5. Registra artefactos modificados.
6. Aplica auto-revision.
7. Guarda episodios en caso de fallo.
8. Ajusta el contexto del siguiente intento.
9. Programa backoff antes de reintentar.

### Artefactos

[artifact_scanner.py](../src/orchestrator/application/artifact_scanner.py) detecta archivos creados, modificados y eliminados, calcula SHA-256 y marca cambios fuera de `allowed_paths`.

### Auto-revision

[auto_reviewer.py](../src/orchestrator/application/auto_reviewer.py) aprueba solo resultados verificables. Para planes financieros exige datos reales, costes incluidos, validacion fuera de muestra y umbrales de retorno/drawdown.

### Aprendizaje

[learning_engine.py](../src/orchestrator/application/learning_engine.py) clasifica fallos de timeout, sintaxis, dependencias, validacion y seguridad. Usa episodios previos para generar contexto breve de reintento.

### Objetivos

[goal_engine.py](../src/orchestrator/application/goal_engine.py) crea objetivos raiz, asocia tareas y calcula progreso por tareas completadas.

### Supervisores por plan

[server.py](../src/orchestrator/interfaces/mcp/server.py) usa un supervisor dedicado por plan en lugar de un unico hilo global. Cada plan mantiene su SQLite y su GoalTree.

### CLI

Se añadieron:

```powershell
maoq task recover --max-age-seconds 300
maoq plan status <plan_id>
```

## Validacion

- Suite completa: `14 passed`.
- Compilacion: `python -m compileall -q src`.
- Comprobacion estatica: sin errores en los archivos modificados.
- Las advertencias restantes proceden de `pydantic-settings` y `pytest-asyncio`.

## Limites conocidos

- Cline necesita CLI o bridge headless configurado; la extension por si sola no basta.
- El heartbeat se basa en timestamps persistidos; un heartbeat de subprocess completamente independiente es una mejora futura.
- La deteccion de diffs usa hashes y no genera todavia un diff textual Git completo.
- Las bases SQLite locales de `data/plans` no se publican en Git.
