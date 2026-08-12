# Arquitectura

Copilot produce planes compactos y los entrega como tareas. El orquestador valida el contrato, persiste la tarea en SQLite y un worker selecciona por prioridad y dependencias. El adapter ejecuta Kilo, Cline o un fake de pruebas. Copilot revisa el resultado, aporta feedback y decide si libera la siguiente tarea o solicita otra iteracion. Solo se conserva un resumen, salida truncada, estado y feedback para controlar el consumo de tokens.

```text
Copilot planner -> MCP -> TaskStore(SQLite) -> Worker -> Executor(Kilo/Cline/Simulated)
    ^                                                   |
    +---------- resumen + feedback + revision ----------+
```

La primera version usa subprocess por ser portable en Windows. Kilo API/ACP, Cline SDK y un broker externo se incorporaran tras validar el flujo local.

El `workspace` de cada tarea es un proyecto objetivo externo. El orquestador no
importa ni contiene la logica del proyecto objetivo: ejecuta agentes dentro de
ese workspace y conserva solo estados, resultados, validaciones y feedback.
