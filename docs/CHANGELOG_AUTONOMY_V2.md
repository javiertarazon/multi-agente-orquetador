# Cambios documentados: Autonomia v2

Fecha: 2026-08-21

## Correcciones (2026-08-21)

- **Validaciones Windows-compatible**: Reemplazado `subprocess.run()` con `Popen` + `CREATE_NEW_PROCESS_GROUP` + `kill()` para timeout robusto en Windows (evita procesos huérfanos y timeouts silenciosos).
- **Timeout de validación acotado**: Máximo 300s (5 min) configurable por tarea, antes usaba `task.timeout_seconds` completo (hasta 900s).
- **Manejo de procesos huérfanos**: `_run_validation_process` usa `Popen.communicate(timeout)` + `proc.kill()` para limpieza garantizada en Windows.
- **Tests actualizados**: Mock migrado de `subprocess.run` a `_run_validation_process` con `_ValidationOutcome` dataclass.
- **Tests pasan**: 65/65 tests pasando (antes 1 fallaba por timeout).

## Nuevas funciones (2026-08-21)

### Validaciones robustas Windows (`worker.py`)

- **`_ValidationOutcome`**: Dataclass con `exit_code`, `stdout`, `stderr`, `timed_out` para resultados estructurados.
- **`_run_validation_process`**: Función reutilizable para ejecutar validaciones con timeout robusto, manejo de `FileNotFoundError` (exit_code=127) y `TimeoutExpired` (exit_code=124).
- **Limpieza de procesos**: `proc.kill()` + `communicate(timeout=15)` garantiza limpieza de procesos y pipes en Windows.

### Validación de agentes nativos gratuitos (2026-08-21)

- **Kilo**: Modelo nativo `kilo/cohere/north-mini-code:free` (sin API key) - funcionando ✅
- **Hermes**: NVIDIA Nemotron 3 Super 120B free vía OpenRouter (`nvidia/nemotron-3-super-120b-a12b:free`) con `OPENROUTER_API_KEY` ✅
- **Cline**: Provider `cline` con `anthropic/claude-sonnet-5` ✅

### Configuración de modelos nativos (`config/default.yaml`)

```yaml
kilo_model: kilo/cohere/north-mini-code:free
hermes_model: ""
hermes_provider: ""
cline_model: anthropic/claude-sonnet-5
cline_provider: cline
```

### Variables de entorno (`.env`)

```env
NVIDIA_API_KEY=nvapi-...
OPENROUTER_API_KEY=sk-or-...
MAOQ_KILO_BIN=C:/Users/javier/AppData/Roaming/npm/kilo.cmd
MAOQ_CLINE_BIN=C:/Users/javier/AppData/Roaming/npm/cline.cmd
MAOQ_HERMES_BIN=C:/Users/javier/.local/bin/hermes.CMD
```

## Verificación funcional completa (2026-08-21)

### Tests
- Suite completa: **65/65 tests passing** (antes 64/65)
- Compilación: `python -m compileall -q src` - OK
- Linting: `ruff check src tests` - OK

### Auditoría funcional end-to-end

1. **Agentes individuales**: Kilo, Hermes, Cline - todos `succeeded` con modelos nativos gratuitos
2. **Plan E2E simple** (3 tareas paralelas): 3/3 `succeeded` - validaciones de existencia de archivos
3. **Loop de aprendizaje**: 1 tarea succeeded + 1 failed intencional → **1 episodio generado** y persistido en SQLite
4. **Memoria persistente**: Episodios aparecen en `session_summary.lecciones`
5. **Resume/Retry**: `resume_plan` funciona correctamente (plan completado → 0 pendientes)
6. **Ejecución paralela**: `run_parallel(max_workers=2)` con ThreadPoolExecutor funcionando

### Capacidades verificadas

| Capacidad | Estado | Detalle |
|-----------|--------|---------|
| Kilo (modelo nativo free) | ✅ | `kilo/cohere/north-mini-code:free` |
| Hermes (NVIDIA via OpenRouter) | ✅ | `nvidia/nemotron-3-super-120b-a12b:free` |
| Cline (provider cline) | ✅ | `anthropic/claude-sonnet-5` |
| Validaciones robustas Windows | ✅ | Popen + kill + timeout 300s |
| Ejecución paralela | ✅ | `run_parallel(max_workers=2)` |
| Memoria persistente (episodios) | ✅ | SQLite por plan |
| Loop de aprendizaje | ✅ | Episodios → `session_summary.lecciones` |
| Resume/Retry | ✅ | `resume_plan`, backoff exponencial |
| Supervisión por plan | ✅ | MCP server con aislamiento |

## Validación

- Suite completa: **65/65 tests passing**
- Compilación: `python -m compileall -q src` - OK
- Linting: `ruff check src tests` - OK
- Auditoría funcional: 3/3 tareas E2E succeeded + loop aprendizaje funcionando

## Limites conocidos

- Cline necesita CLI o bridge headless configurado; la extension por si sola no basta.
- El heartbeat se basa en timestamps persistidos; un heartbeat de subprocess completamente independiente es una mejora futura.
- La deteccion de diffs usa hashes y no genera todavia un diff textual Git completo.
- Las bases SQLite locales de `data/plans` no se publican en Git.
- Los modelos nativos gratuitos pueden tener límites de rate/latencia superiores a APIs pagadas.

---

## Correcciones (2026-08-13)

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
