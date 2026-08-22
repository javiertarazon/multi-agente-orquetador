# Modo enjambre y modo dios

Las tareas del orquestador pueden ejecutarse de forma normal o redundante.

## Activación

Añade uno de estos tags a la tarea:

- `enjambre`
- `swarm`
- `modo_dios`

El worker detecta el tag y usa `AgentGateway.swarm_round`. Kilo, Hermes y Cline
reciben la misma tarea en paralelo. Se selecciona una respuesta exitosa; si
ningún agente termina correctamente, se ejecuta el orden de fallback normal.

## Ejemplo

```json
{
  "prompt": "Implementa y prueba la mejora",
  "executor": "cline",
  "tags": ["enjambre"],
  "validation_commands": [["python", "-m", "pytest", "-q"]],
  "max_retries": 1
}
```

`modo_dios` es un alias operativo de enjambre, no una eliminación de límites.
Continúan activos seguridad, workspaces, validaciones, timeouts, cuotas y
revisión humana.

## Skills y MCP

OpenCode, Cline, Kilo y Hermes pueden usar sus skills y servidores MCP nativos
si están instalados y habilitados en sus propias configuraciones. El
orquestador transporta el prompt, contexto, artefactos y validaciones; no
simula una skill que el agente no tenga.

## Limitación actual

El selector actual prioriza resultados exitosos y evidencia de salida. Para
producción crítica conviene añadir una tarea de revisión posterior con
validaciones independientes; el texto más largo no demuestra corrección.
