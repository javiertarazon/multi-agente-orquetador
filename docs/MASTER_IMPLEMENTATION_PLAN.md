# Plan maestro de implementación: orquestador autónomo multiagente

## 1. Objetivo

Convertir este repositorio en una plataforma local, reproducible y económica
para que un agente principal (Copilot, o un adaptador alternativo como Codex,
Kiro, Antigravity u OpenCode) planifique y supervise, mientras Kilo y Cline
ejecutan tareas en un workspace aislado. El sistema debe:

- continuar sin pedir al usuario que vuelva a iniciar cada paso;
- usar modelos gratuitos cuando estén disponibles, con fallback configurable;
- conservar memoria persistente, resúmenes y evidencia de cada intento;
- probar, evaluar, corregir y volver a probar hasta alcanzar criterios objetivos;
- detenerse de forma segura ante límites, ambigüedad o riesgo financiero;
- ser utilizable tanto por CLI como por MCP y fácil de operar en Windows.

Este plan no autoriza operaciones reales de trading. El modo productivo debe
permanecer bloqueado hasta que exista una aprobación explícita, credenciales
separadas y pruebas de seguridad independientes.

## 2. Estado actual confirmado

Ya existen piezas importantes: tareas con dependencias y prioridades, SQLite,
worker, supervisión por plan, ejecutores simulated/Kilo/Cline, validaciones,
escaneo de artefactos, episodios de aprendizaje, GoalTree, recuperación de
tareas, políticas de revisión y una interfaz MCP.

Las limitaciones visibles son: el contrato de proveedores alternativos todavía
no está unificado, la continuidad autónoma depende del proceso worker, falta un
estado operacional resumido para reanudar tras reinicio, faltan pruebas de
contrato y de fallos de los CLIs, y la política de presupuesto de tokens debe
ser explícita por tarea, fase y proveedor.

## 3. Arquitectura objetivo

```text
Agente principal/planner
        |
        v
Plan contract -> Supervisor -> Scheduler -> Agent gateway
                      |              |          |
                 SQLite/memoria   sandbox   Kilo | Cline | fallback
                      |              |          |
                 evaluator <------- evidencia --+
                      |
              pass / repair / escalate / stop
```

El agente principal no debe ejecutar código arbitrario directamente. Debe
producir un contrato de plan versionado con objetivo, tareas, dependencias,
criterios de aceptación, presupuesto, política de riesgo y condiciones de
parada. El gateway será el único punto que conoce los CLIs concretos; así se
puede cambiar Copilot por Codex, Kiro, Antigravity u OpenCode sin reescribir el
dominio.

## 4. Fases y tareas

### Fase 0 — Línea base y contratos (P0)

1. Ejecutar la suite con `.venv`, corregir regresiones y registrar baseline.
2. Definir esquemas Pydantic para `PlanContract`, `TaskContract`,
   `AttemptReport`, `EvaluationReport`, `TokenBudget` y `StopReason`.
3. Añadir `schema_version`, `correlation_id`, `plan_id` y `attempt_id` a todos
   los eventos persistidos y a los logs.
4. Documentar una matriz de capacidades: planner, executor, reviewer,
   sandbox, memoria y soporte de streaming por proveedor.

### Fase 1 — Gateway de agentes y modelos gratuitos (P0)

1. Crear una interfaz única `AgentProvider` con `plan`, `execute`, `review` y
   `summarize`.
2. Implementar adaptadores Kilo y Cline sobre la interfaz actual, incluyendo
   detección de binario, timeout, cancelación, códigos de salida y JSON mal
   formado.
3. Añadir adaptadores opcionales para Codex/Kiro/Antigravity/OpenCode sin
   acoplarlos al dominio: configuración por comando, variables de entorno y
   capacidades declaradas.
4. Definir fallback ordenado: Kilo gratuito -> Cline gratuito -> simulated;
   nunca cambiar silenciosamente a un modelo de pago.
5. Añadir circuit breaker por proveedor cuando haya errores repetidos o cuota
   agotada.

### Fase 2 — Autonomía y scheduler (P0)

1. Hacer que el supervisor sea reanudable: heartbeat, lease, recuperación y
   estado `paused_waiting_review` persistido.
2. Añadir un modo `run-until-terminal` con límites de tiempo, iteraciones,
   costo estimado, tokens y cambios máximos.
3. Desbloquear dependientes sólo después de evaluación objetiva y revisión según
   política; los fallos deben generar automáticamente una tarea de reparación.
4. Permitir concurrencia sólo entre tareas sin dependencia ni conflicto de
   archivos, con locks por workspace.
5. Implementar cancelación segura y cierre ordenado al reiniciar Windows.

### Fase 3 — Sandbox y seguridad (P0)

1. Cada intento debe usar worktree o copia temporal del workspace objetivo.
2. Aplicar allowlist de rutas, comandos, procesos, red y tamaño de artefactos.
3. Capturar diff, hashes, stdout/stderr truncados y resultado de cada comando.
4. Prohibir credenciales en prompts, logs y artefactos; cargar secretos sólo
   desde el entorno del proceso.
5. Mantener `paper_trading` como único modo por defecto; bloquear broker,
   retiros, órdenes reales y claves de producción.

### Fase 4 — Evaluación y aprendizaje (P0)

1. Separar evaluación técnica, funcional, seguridad y financiera.
2. Generar un `EvaluationReport` con pruebas ejecutadas, métricas, fallos,
   confianza, evidencia y decisión.
3. Ante fallo, ejecutar una reflexión estructurada: qué criterio falló, causa
   probable, evidencia, corrección mínima y prueba de no regresión.
4. Guardar episodios compactos; deduplicar por hash de error y evitar enviar al
   modelo más de los últimos episodios relevantes.
5. Aplicar backoff y límite de reparación; después escalar al agente principal
   con un resumen accionable, no con el log completo.

### Fase 5 — Gestión de contexto y tokens (P1)

1. Presupuestar tokens por plan, tarea, intento y proveedor.
2. Usar contexto por capas: contrato -> resumen del workspace -> diff -> error
   actual -> episodios relevantes.
3. Comprimir automáticamente salidas largas y conservar el original sólo en
   disco, con hash y retención configurable.
4. Evitar duplicar instrucciones entre Copilot, Kilo y Cline.
5. Añadir métricas de tokens estimados, ratio de compresión, reintentos y costo
   por resultado.

### Fase 6 — Operación y UX (P1)

1. Crear comandos `maoq plan run`, `maoq plan pause`, `maoq plan resume`,
   `maoq plan explain` y `maoq doctor --agents`.
2. Mejorar `plan status` con progreso, tarea actual, proveedor, intento,
   presupuesto restante, último fallo y próxima acción.
3. Exponer por MCP sólo operaciones idempotentes y con permisos explícitos.
4. Añadir exportación de informe Markdown/JSON para auditoría.
5. Proporcionar un quickstart con simulated, luego Kilo y finalmente Cline.

### Fase 7 — Validación del bot trader (P1)

1. Definir datasets versionados y separación train/validation/test temporal.
2. Exigir costos, slippage, comisiones, out-of-sample y data provenance.
3. Ejecutar walk-forward, stress tests y pruebas de sensibilidad.
4. No aceptar retorno como éxito sin drawdown, riesgo, estabilidad y evidencia.
5. Sólo después de pasar paper trading prolongado evaluar una revisión humana
   independiente para cualquier conexión real.

## 5. Bucle autónomo de decisión

```text
plan -> ejecutar -> validar -> evaluar
                         |
          +--------------+--------------+
          |                             |
        PASS                      FAIL / UNCERTAIN
          |                             |
    siguiente tarea       diagnosticar -> reparar -> revalidar
          |                             |
      terminal                   límite alcanzado -> escalar/parar
```

Cada iteración debe responder internamente: “¿qué objetivo no se logró?, ¿qué
evidencia lo demuestra?, ¿cuál es la hipótesis de causa?, ¿cuál es el cambio
mínimo?, ¿qué prueba evita repetir el error?”. Si no puede responder con
evidencia, debe marcar `uncertain` y solicitar revisión, no inventar éxito.

## 6. Criterios de aceptación de la plataforma

- Un plan de ejemplo termina con simulated sin intervención después de iniciar
  el worker.
- Un fallo reproducible genera episodio, reparación y prueba de regresión.
- Reiniciar el proceso no pierde tareas, leases, memoria ni progreso.
- Un proveedor caído activa fallback sin usar un modelo de pago.
- Ninguna tarea fuera de `allowed_paths` puede modificar el workspace.
- Se puede explicar por qué una tarea pasó, falló, se reintentó o se detuvo.
- Los límites de tokens/iteraciones/tiempo siempre se respetan.
- El escenario financiero de ejemplo rechaza métricas incompletas o no
  out-of-sample.

## 7. Orden recomendado de ejecución

Primero Fase 0, luego Fases 1–4 en orden; son el núcleo de confiabilidad.
Después Fases 5–6 para eficiencia y usabilidad. La Fase 7 debe ejecutarse en
un workspace del bot trader separado y sólo en paper trading.

## 8. Próxima acción

La siguiente implementación concreta es Fase 0: correr la suite del entorno
virtual, inventariar fallos y añadir los contratos versionados. Al terminar,
el agente principal puede crear las tareas de Fase 1 y delegarlas al proveedor
disponible, manteniendo una única memoria de plan y un informe por iteración.

## 9. Matriz de ejecución actualizada

| Fase | Estado | Evidencia |
|---|---|---|
| 0. Línea base y contratos | Completada localmente | Contratos Pydantic, Ruff y pruebas |
| 1. Gateway Kilo/Cline | Completada parcialmente | Gateway y ejecutores CLI configurables |
| 2. Scheduler autónomo | Completada parcialmente | `run-until-terminal`, recuperación y backoff |
| 3. Sandbox y seguridad | Completada parcialmente | allowlist, escaneo, bloqueo de live trading |
| 4. Evaluación y aprendizaje | Completada parcialmente | validaciones, episodios y auto-review existentes |
| 5. Tokens y contexto | Completada parcialmente | `TokenBudget` y contexto de reintentos |
| 6. Operación y UX | Completada parcialmente | CLI, MCP, doctor y estados persistentes |
| 7. Bot trader | Pendiente externo | requiere datasets, paper trading y revisión humana |

La única parte que no puede certificarse desde este repositorio es la ejecución
real de los proveedores y del bot trader: depende de CLIs, autenticación,
modelos, datos y un workspace externo. Los tests usan proveedores simulados para
verificar el contrato sin consumir cuota ni realizar operaciones financieras.
