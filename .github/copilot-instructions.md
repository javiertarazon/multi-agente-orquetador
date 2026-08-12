# Multi Agente Orquestado

## Flujo obligatorio y compuerta de delegacion

Cuando el usuario solicite cambios de programacion:

1. El primer paso es siempre Plan Mode. No invoques ninguna herramienta MCP durante la planificacion.
2. No ejecutes cambios ni crees tareas durante la planificacion.
3. Presenta el plan y espera una aprobacion explicita del usuario.
4. Despues de que el usuario apruebe el plan, pregunta literalmente: **"¿Quieres delegar este plan a Multi Agente Orquestado para que Kilo y Cline lo ejecuten?"**
5. Mientras no exista una respuesta afirmativa a esa pregunta, no llames al servidor MCP `multi-agente-orquestado`, no uses `create_plan` y no ejecutes cambios.
6. Solo si el usuario responde afirmativamente, usa `create_plan` con `auto_execute: true`.
7. Envia el plan completo, no la conversacion completa.
8. Define cada tarea con `prompt`, `executor`, `depends_on`, `allowed_paths` y `validation_commands`.
9. Usa `kilo` para implementacion y `cline` para revision o pruebas cuando sea apropiado.
10. Consulta `list_tasks` y `get_task` para supervisar resultados compactos.

### Regla de parada

La disponibilidad del MCP no implica permiso para usarlo. Si el usuario no ha seleccionado Plan Mode, debes limitarte a indicar que debe activarlo en el selector de modo de Copilot. Si ya existe un plan, debes mostrarlo y esperar confirmacion; nunca debes saltar directamente a `create_plan`.

## Formato de importacion

```json
{
  "plan": "Resumen del plan aprobado",
  "workspace": ".",
  "tasks": [
    {
      "prompt": "Implementar ...",
      "executor": "kilo",
      "depends_on": [],
      "allowed_paths": ["src/", "tests/"],
      "validation_commands": [["python", "-m", "pytest", "-q"]]
    }
  ]
}
```

Al importar con `auto_execute: true`, el MCP inicia el worker automaticamente. Esta opcion solo se puede usar despues de la aprobacion del plan y de la confirmacion afirmativa de delegacion. Copilot debe consultar `list_tasks` y `get_task` para supervisar resultados y crear nuevas tareas de correccion si es necesario. Usa `auto_execute: false` si el usuario solicita revisar el plan antes de ejecutar.