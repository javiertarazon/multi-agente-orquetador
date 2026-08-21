# Plan profesional del multi-agente-orquestador

## Objetivo

Mantener una cadena reproducible `OpenCode -> MCP -> supervisor -> worker` con
Kilo, Cline y Hermes, usando primero los proveedores nativos configurados por
cada CLI y NVIDIA como fallback explícito. El sistema debe ser observable,
recuperable, seguro y verificable sin exponer secretos.

## Diseño operativo

1. OpenCode se conecta al servidor MCP local definido en `opencode.json`.
2. MCP crea planes aislados por base SQLite y conserva tareas, intentos,
   notificaciones, artefactos y episodios de aprendizaje.
3. El supervisor ejecuta tareas respetando dependencias, prioridades,
   reintentos, límites de tiempo y políticas de aprobación.
4. Cada worker usa su configuración nativa:
   - Kilo: `kilo/cohere/north-mini-code:free`.
   - Cline: proveedor `cline`, modelo `anthropic/claude-sonnet-5`.
   - Hermes: configuración de `~/.hermes/config.yaml`.
5. NVIDIA se activa por tarea o entorno con `MAOQ_*_PROVIDER=nvidia`,
   `MAOQ_*_MODEL=nvidia/nemotron-3-super-120b-a12b` y `NVIDIA_API_KEY`.

## Variables y controles

- `MAOQ_DB_PATH`, `MAOQ_WORKSPACE_ROOT`: persistencia y límites de workspace.
- `MAOQ_MAX_WORKERS`: concurrencia del supervisor.
- `MAOQ_KILO_BIN`, `MAOQ_CLINE_BIN`, `MAOQ_HERMES_BIN`: binarios explícitos.
- `MAOQ_*_MODEL` y `MAOQ_*_PROVIDER`: overrides por proveedor.
- `NVIDIA_API_KEY`, `OPENROUTER_API_KEY` y claves nativas: nunca se versionan.
- Cada subprocess tiene timeout, captura limitada y detección de salida vacía.

## Criterios de aceptación

- `maoq opencode doctor` informa MCP y agente correctamente.
- `opencode mcp list` muestra el servidor conectado.
- Las pruebas unitarias pasan sin excepciones de threads.
- Kilo, Cline y Hermes responden `OK` en una prueba mínima autenticada.
- Una tarea creada por MCP termina en `succeeded` y deja notificaciones.
- Un fallo de proveedor produce un resultado explícito y permite fallback o
  reintento sin bloquear el proceso.

## Ejecución

La evidencia de la ejecución de este plan se registra en
`docs/EXECUTION_REPORT.md` y debe actualizarse con fecha, versiones, comandos,
resultado y cualquier limitación externa (cuota, autenticación o red).
