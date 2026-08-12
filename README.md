# Multi Agente Orquestado

Plataforma local y agnostica del dominio para que Copilot planifique, delegue ejecucion de codigo a Kilo Code o Cline y revise los resultados mediante SQLite, CLI y MCP.

## Inicio rapido

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
maoq init
maoq doctor
maoq task create "Crear una prueba de humo" --executor simulated
maoq worker run --once
maoq task list
pytest -q
```

Kilo y Cline son opcionales para el MVP. Sus adaptadores usan subprocess y se activan solo cuando se seleccionan explicitamente.

## Principios

- Copilot planifica y supervisa mediante tareas y MCP.
- La creacion del plan no ejecuta agentes automaticamente; Copilot solicita confirmacion antes de delegar.
- Kilo ejecuta tareas autonomas cuando esta instalado.
- Cline ejecuta tareas headless como alternativa.
- El orquestador limita comandos, tiempo, salida y reintentos.
- Copilot decide si el resultado pasa o requiere otra iteracion.
- Los resultados se resumen y truncan para reducir tokens y preservar trazabilidad.
- El feedback de revision se conserva para construir el siguiente prompt sin repetir contexto innecesario.

Consulta `docs/ARCHITECTURE.md` y `docs/AGENT_INTEGRATION.md`.

## Capacidades actuales

- Planes de tareas con dependencias, prioridades, reintentos y políticas de revisión.
- Ejecución mediante Kilo, Cline o un ejecutor simulado para pruebas.
- Validación automática mediante comandos declarados por tarea.
- Persistencia SQLite y notificaciones de inicio, reintento, fallo y finalización.
- Aislamiento por plan: cada plan creado por MCP usa `data/plans/<plan_id>.db`.
- Supervisión del plan dentro del proceso MCP hasta que sus tareas terminan,
  fallan definitivamente o se cancelan.
- Herramienta `get_plan_status` para consultar avance, objetivos y ciclo actual.
- Compatibilidad con workspaces externos: el orquestador coordina el trabajo,
  pero no mezcla su código con el proyecto objetivo.

## Flujo autónomo

1. Copilot define el plan, los agentes y las condiciones de aceptación.
2. `create_plan` crea las tareas en una SQLite aislada y conserva los objetivos.
3. `execute_plan` activa el supervisor del plan.
4. El supervisor reclama tareas, ejecuta Kilo/Cline, valida sus comandos y
	respeta las dependencias.
5. Las tareas externas quedan disponibles para revisión de Copilot antes de
	liberar sus dependientes.
6. Un ciclo posterior puede crear una nueva iteración con el feedback y las
	métricas del resultado. El orquestador no declara rentabilidad sin evidencia
	de backtest histórico.

Para un bot trader, las condiciones pueden expresarse como retorno mínimo,
drawdown máximo y número máximo de iteraciones. La estrategia, los datos y el
backtest viven en el workspace del bot, mientras este repositorio conserva el
estado, las validaciones y la trazabilidad del plan.

## Arranque MCP

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[mcp]"
python -m orchestrator.interfaces.mcp.server
```

El servidor usa transporte MCP `stdio`, adecuado para clientes locales como
Copilot, Kilo y Cline. Para ejecución local del worker:

```powershell
maoq worker --once
```

Consulta `docs/SUPERVISION.md` para el diseño de aislamiento y supervisión.

Los proyectos que reciben trabajo son externos a esta plataforma. Por ejemplo,
un bot trader debe vivir en su propio workspace; esta aplicación solo lo
planifica, delega y revisa. Consulta `docs/PROJECT_BOUNDARIES.md`.
