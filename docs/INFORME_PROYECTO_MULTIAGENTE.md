# Informe del proyecto: Multi-Agente Orquestado

Fecha: 2026-08-21

## 1. Resumen ejecutivo

El proyecto integra OpenCode como planificador y analista con un orquestador MCP capaz de distribuir tareas entre Cline CLI, Kilo CLI y Hermes CLI. Se corrigieron problemas de descubrimiento de ejecutables, selección de modelos, uso de fallback NVIDIA, timeouts en Windows, validaciones, supervisión y lanzamiento desde el escritorio.

La prueba E2E confirmó el flujo completo: OpenCode crea un plan, Cline ejecuta una tarea, la validación detecta un error, OpenCode analiza el resultado, crea un plan de corrección y el agente vuelve a ejecutar hasta conseguir una validación exitosa.

## 2. Arquitectura y flujo

```text
OpenCode
   │ crea planes, analiza resultados y decide mejoras
   ▼
Servidor MCP del orquestador
   │ health, create_plan, get_task, get_plan_status,
   │ get_episodes y get_artifact
   ▼
Supervisor / Worker
   │ cola, prioridades, dependencias, reintentos y validaciones
   ├── Cline CLI
   ├── Kilo CLI
   └── Hermes CLI
          │
          └── fallback NVIDIA/OpenRouter cuando el proveedor primario falla
```

El ciclo normal es:

1. OpenCode define el objetivo y los criterios de aceptación.
2. `create_plan` registra el plan y sus tareas.
3. El supervisor asigna las tareas al ejecutor indicado.
4. El agente modifica el workspace.
5. El worker ejecuta las validaciones declaradas.
6. Se guardan resultado, artefactos, errores y episodios de aprendizaje.
7. OpenCode consulta el estado y decide si el objetivo fue alcanzado.
8. Si falla, crea un plan de corrección con las lecciones del plan anterior.

## 3. Correcciones y mejoras realizadas

### Agentes y modelos

- Se verificó la instalación global de Cline CLI `3.0.56`.
- Se verificó la instalación global de Kilo CLI `7.4.22`.
- Se corrigió el descubrimiento del ejecutable de Cline en Windows mediante `MAOQ_CLINE_BIN`.
- Se probaron los adaptadores de Cline, Kilo y Hermes.
- Hermes se probó usando fallback NVIDIA y completó correctamente.
- Se mantuvieron los modelos nativos configurados por cada CLI cuando están disponibles.
- NVIDIA/OpenRouter queda como respaldo configurable, no como sustituto obligatorio del modelo nativo.

### Windows y estabilidad

- Los procesos de agentes usan grupo de procesos y ejecución sin ventana.
- Los procesos hijos se terminan de forma controlada al alcanzar el timeout.
- Se limitó el tiempo de validación a un máximo de 300 segundos, respetando valores menores configurados por cada tarea.
- Se añadió una prueba regresiva para evitar que una validación larga bloquee el supervisor.
- Se corrigieron situaciones de `ENOENT` relacionadas con ejecutables globales de Cline.

### Orquestación

- Cola de tareas con prioridades.
- Ejecución paralela de tareas independientes.
- Dependencias entre tareas.
- Reintentos configurables.
- Políticas de aprobación y revisión.
- Registro de resultados, artefactos y episodios.
- Clasificación de fallos, incluidos los timeouts.
- Consulta del estado del plan mediante MCP.

### Lanzadores de Windows

Se crearon accesos directos en el escritorio:

- `Cline CLI - Multi Agente Orquestado.lnk`
- `Kilo CLI - Multi Agente Orquestado.lnk`

Scripts reproducibles:

- `scripts/launch-cline.cmd`
- `scripts/launch-kilo.cmd`

Ambos abren el CLI desde la raíz del proyecto y aceptan argumentos adicionales.

## 4. Prueba E2E realizada

Workspace de prueba:

`workspace/e2e_open_code_loop2`

### Fase de fallo intencional

- Plan: `b79d24e86c0245a9a43f5a36d3defc12`
- Tarea: `e0fd0de9a16c41d79aef5c6461946108`
- Cline creó `answer.txt` con `WRONG`.
- `check_right.py` esperaba `RIGHT`.
- La validación terminó con `exit_code 1`.
- El plan quedó correctamente en estado `failed`.

### Fase de aprendizaje y corrección

- OpenCode consultó la tarea, el plan, el artefacto y la validación.
- Creó un nuevo plan usando `lessons_from`.
- Plan de corrección: `0a8dd7ab250946dcbfda07948e684871`.
- Cline cambió el archivo a `RIGHT`.
- La validación terminó con `RIGHT_OK`.
- El plan quedó en estado `succeeded`.

Esta prueba demuestra el loop de mejora dirigido por OpenCode. El servidor registra las lecciones y permite crear planes derivados; la decisión de crear el siguiente plan la toma el agente planificador.

## 5. Cómo usar el sistema

### Comprobar herramientas instaladas

```powershell
cline --version
kilo --version
hermes --version
opencode --version
```

### Usar los lanzadores

Abrir desde el escritorio el acceso directo de Cline o Kilo. También se pueden ejecutar desde PowerShell:

```powershell
scripts\launch-cline.cmd
scripts\launch-kilo.cmd
```

Para pasar una instrucción al CLI:

```powershell
scripts\launch-cline.cmd "Revisa el proyecto y ejecuta las pruebas"
scripts\launch-kilo.cmd "Analiza este error y propón una corrección"
```

### Ejecutar el orquestador

El proyecto debe tener disponibles las variables de entorno configuradas en `.env`. Las claves nunca deben añadirse al repositorio.

OpenCode debe conectarse al servidor MCP del orquestador. Desde allí puede utilizar las operaciones de salud, creación de planes, estado, tareas, episodios y artefactos.

Un plan profesional debe declarar:

- objetivo concreto;
- workspace absoluto o inequívoco;
- ejecutor (`cline`, `kilo`, `hermes` o simulado);
- comandos de validación;
- timeout;
- número de reintentos;
- política de revisión;
- criterios de éxito observables.

## 6. Ventajas

- Permite combinar varios agentes especializados.
- Reduce el trabajo manual de supervisión.
- Usa validaciones objetivas en lugar de confiar solo en el texto del agente.
- Puede recuperarse de fallos mediante planes de corrección.
- Registra artefactos y diagnósticos para auditoría.
- Tiene fallback de proveedor cuando el modelo primario no responde.
- Los timeouts y procesos Windows están controlados.
- Las tareas independientes pueden ejecutarse en paralelo.
- Los lanzadores facilitan el uso diario por parte de operadores no técnicos.

## 7. Desventajas y límites

- Los modelos gratuitos o de fallback pueden tener límites de cuota, velocidad y contexto.
- NVIDIA/OpenRouter depende de conectividad y de una clave válida.
- El fallback no garantiza que todos los modelos tengan las mismas capacidades o calidad.
- Un agente puede declarar que terminó aunque la tarea sea incorrecta; por eso siempre deben existir validaciones.
- El loop de mejora requiere que OpenCode analice el fallo y cree el plan siguiente; no debe asumirse que todos los fallos generan automáticamente otro plan sin esa decisión.
- La ejecución paralela consume más recursos y puede provocar conflictos si dos tareas modifican los mismos archivos.
- Los timeouts protegen el sistema, pero una tarea legítima que necesite más de 300 segundos de validación requerirá una política específica.
- Las claves en `.env` son sensibles y deben rotarse si se exponen o se comparten.

## 8. Estado de pruebas

Suite completa ejecutada:

`65 passed`

También se verificaron individualmente:

- Cline CLI `3.0.56`.
- Kilo CLI `7.4.22`.
- Hermes mediante fallback NVIDIA.
- Conexión MCP y operación `health`.
- Flujo E2E de fallo, análisis, corrección y validación.
- Lanzadores de escritorio.

Persisten advertencias no bloqueantes de dependencias (`pydantic`, `pytest-asyncio` y caché de pytest).

## 9. Commits publicados

- `5ffae2d` — endurecimiento de orquestación y workers nativos.
- `d459dcf` — timeouts acotados para procesos Windows.
- `6f3602f` — límite de timeout para validaciones.
- `51e2b1c` — lanzadores Windows para Cline y Kilo.

Los últimos cambios fueron subidos a la rama remota `fix/validation-timeout`.

## 10. Recomendaciones de operación

1. Definir siempre validaciones ejecutables y reproducibles.
2. Usar workspaces aislados por plan cuando haya ejecución paralela.
3. Revisar los artefactos después de cada tarea importante.
4. Configurar reintentos solo para fallos recuperables.
5. Mantener el modelo nativo como primera opción y NVIDIA/OpenRouter como respaldo.
6. Rotar las claves periódicamente y no subir `.env` al repositorio.
7. Crear un Pull Request desde `fix/validation-timeout` antes de fusionar a la rama principal.
