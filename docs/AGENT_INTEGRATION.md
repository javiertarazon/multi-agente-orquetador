# Integracion de agentes

## Kilo
Seleccionar `--executor kilo`. El adapter invoca `kilo run --auto <prompt>` en el workspace de la tarea y descubre automaticamente el binario incluido en la extension VS Code de Kilo. Por defecto usa `kilo/cohere/north-mini-code:free`, que esta marcado por Kilo como gratuito. Se puede fijar la ruta con `MAOQ_KILO_BIN` y otro modelo con `MAOQ_KILO_MODEL`.

Si Kilo devuelve `Add credits to continue`, la integracion local funciona pero la cuenta/proveedor seleccionado no tiene cuota habilitada; el orquestador conserva ese error en `stderr` y marca la tarea como `failed`.

## Cline
Seleccionar `--executor cline`. El adapter usa el CLI instalado con `cline --json
--auto-approve true --cwd <workspace> <prompt>` y captura su salida JSON.

La extension de VS Code no es el canal usado por el worker. Para ejecucion
headless se instala el CLI de Cline:

```powershell
npm install -g cline
maoq worker --once
```

El CLI puede requerir configurar un proveedor/modelo con `cline auth` o mediante
la configuracion de Cline. Si no hay autenticacion, el executor conserva el error
del CLI y marca la tarea como `failed`; no intenta automatizar la UI.

## Copilot
Copilot es el planner y reviewer: crea planes compactos por MCP, pregunta al usuario si desea delegarlos, y solo despues llama a `execute_plan`. Asigna cada tarea a Kilo o Cline, inspecciona resumen/validaciones y usa `review_task` con feedback para aprobar o pedir una nueva iteracion. No se asume una API publica para controlar sus sesiones desde Python; el MCP es el contrato estable.

Flujo obligatorio en modo Plan:
1. Copilot prepara el plan y lo muestra al usuario.
2. Copilot pregunta: `El plan esta listo. ¿Quieres ejecutarlo con multi agente orquestado usando Kilo y Cline?`
3. Solo con una respuesta afirmativa llama a `execute_plan`.
4. Copilot consulta resultados, artefactos y validaciones.
5. Si falla, rechaza con feedback y crea una iteracion corregida.
6. Si pasa, informa el resultado y solicita confirmacion antes de cualquier nueva fase sensible.

## Bucle de mejora y tokens
1. Copilot envia solo objetivo, restricciones y contexto minimo.
2. El executor trabaja en el workspace y devuelve salida truncada.
3. El worker ejecuta validaciones declaradas.
4. Copilot revisa el resumen y los artefactos, no toda la salida bruta.
5. Si rechaza, el feedback queda persistido para el siguiente prompt.

Los presupuestos de tokens y la seleccion del modelo deben vivir en la configuracion del executor, no en el dominio de la tarea. Kilo puede usar el modelo gratuito configurado y Cline queda como alternativa de ejecucion o revision.

## Seguridad
Usar worktrees para tareas modificadoras, revisar el diff y no habilitar auto-aprobacion en repositorios de produccion.

## Separacion de proyectos
El repositorio `multi agente orquestado` es el coordinador. El repositorio del
bot trader es el workspace objetivo indicado en cada tarea. Kilo y Cline ejecutan
codigo en ese objetivo; no deben convertir el coordinador en un bot trader ni
modificar sus fuentes de referencia sin una tarea explicita.
