# Supervisión autónoma

## Responsabilidades

El MCP es el coordinador del ciclo. Copilot define el plan y revisa resultados;
Kilo y Cline ejecutan tareas dentro del workspace permitido. El worker ejecuta
una tarea por vez, valida sus comandos, registra el resultado y libera las
dependencias solo cuando corresponde.

## Aislamiento SQLite

Cada llamada a `create_plan` genera un identificador y una base independiente:

```text
data/plans/<plan_id>.db
```

Esto evita que tareas antiguas, pruebas o planes de otros proyectos bloqueen la
cola del plan actual. Las herramientas MCP resuelven automáticamente la base
correcta a partir del ID de tarea.

## Supervisión de un plan

`execute_plan` inicia un supervisor asociado a la base del plan. El supervisor
continúa mientras existan tareas pendientes, en ejecución o esperando revisión.
Solo termina cuando todas las tareas quedan `succeeded`, `failed` o `cancelled`.

La herramienta `get_plan_status` devuelve:

- conteo por estado;
- base SQLite utilizada;
- retorno objetivo;
- drawdown máximo permitido;
- número máximo de iteraciones;
- iteración actual.

## Ciclo de mejora

El orquestador conserva el resultado y el feedback de Copilot. Una iteración de
mejora debe entregar métricas estructuradas del backtest, por ejemplo:

```json
{
  "total_return": 0.55,
  "max_drawdown": 0.20,
  "data_source": "historical",
  "costs_included": true
}
```

Copilot aprueba el resultado únicamente si las métricas cumplen el plan. Si no
lo cumplen, crea el siguiente conjunto de tareas para Kilo y Cline con el
feedback y los parámetros que deben corregirse. No se considera válida una
prueba sintética cuando el plan exige datos históricos reales.

## Recuperación

El proceso `maoq worker --once` es una unidad de trabajo y puede ejecutarse por
un servicio externo en Windows si se requiere persistencia después de cerrar
VS Code. El estado permanece en SQLite, por lo que un nuevo worker puede
reanudar la cola sin perder resultados.