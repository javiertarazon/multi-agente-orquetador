# Limites entre proyectos

## Proyecto 1: `multi agente orquestado`

Es la plataforma de coordinacion. Sus responsabilidades son:

- Recibir planes y solicitudes desde Copilot mediante MCP.
- Persistir tareas, dependencias, estados, resultados y feedback.
- Seleccionar y ejecutar Kilo, Cline o un executor de pruebas.
- Ejecutar validaciones declaradas.
- Resumir resultados para reducir tokens.
- Devolver resultados a Copilot para revision y nueva iteracion.

Este proyecto no contiene logica de trading, indicadores, modelos ML, conexion MT5, sizing ni ordenes.

## Proyecto 2: proyecto objetivo

Es el repositorio donde se realiza el trabajo solicitado. Puede ser un bot trader u otro proyecto de codigo. Para el bot trader, el workspace objetivo sera una carpeta nueva separada, por ejemplo:

`D:\datos jt7\proyectos\agentes_autonomos\trade bot\bot-trader-orquestado`

Ese proyecto contiene exclusivamente la implementacion del bot: datos MT5, estrategia, ML, backtest, riesgo, paper trading, tests y configuracion.

## Flujo correcto

1. Copilot analiza la solicitud y revisa los proyectos fuente.
2. Copilot crea un plan MCP con `workspace` igual al proyecto objetivo.
3. El MCP guarda tareas, pero `create_plan` no ejecuta por defecto.
4. Copilot pregunta al usuario si desea delegar el plan.
5. Tras confirmacion, Copilot llama a `execute_plan`.
6. Kilo y Cline trabajan en el workspace objetivo, no en el codigo del orquestador.
7. El orquestador recoge resultados y validaciones.
8. Copilot revisa, aprueba o devuelve feedback para otra iteracion.

## Regla de aislamiento

Los proyectos fuente (`bot-minimax-optimizado-`, `bot-_copilot_ML_4.7` y `mt5-trading-agent-base`) se auditan y sirven como referencia. No son el orquestador ni deben modificarse durante la construccion del bot nuevo, salvo que una tarea lo solicite expresamente y Copilot la apruebe.
