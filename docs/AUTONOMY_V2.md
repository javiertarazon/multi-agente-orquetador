# Autonomia v2

El orquestador ejecuta planes aislados con un supervisor por plan. Copilot define objetivos y criterios; Kilo y Cline trabajan en el workspace de cada tarea; el worker conserva evidencia antes de permitir que el plan avance.

## Loop

1. `create_plan` crea una SQLite aislada, un objetivo raiz y tareas dependientes.
2. El worker reclama una tarea, crea un `TaskAttempt` y captura hashes de las rutas permitidas.
3. El executor produce un resultado y el worker ejecuta las validaciones declaradas.
4. El escaner registra archivos creados, modificados o eliminados.
5. El auto-reviewer aprueba automaticamente solo bajo `auto_on_pass`; `manual`, `always` y los hitos esperan revision.
6. Un fallo queda guardado como `Episode`. El siguiente intento recibe contexto breve y se programa con backoff exponencial.
7. El GoalTree actualiza su progreso segun las tareas aprobadas.

## Politicas

- `auto_on_pass`: continua si todas las comprobaciones objetivas pasan.
- `manual` y `always`: requieren `review_task`.
- `milestone`: requiere revision solo si la tarea tiene el tag `milestone`.
- `sensitive`: mantiene el comportamiento historico y requiere revision para Kilo/Cline.

## Evidencia financiera

Una tarea que declara `target_return` o `max_drawdown` debe publicar metricas estructuradas con `data_is_real`, `costs_included` y `out_of_sample`. Si cualquiera falta o es falso, el resultado es rechazado aunque las pruebas tecnicas pasen.

## Operacion

`maoq task recover` recupera tareas sin heartbeat. `maoq plan status <plan_id>` muestra estados y objetivos de la SQLite aislada. `get_plan_status` expone la misma informacion por MCP.