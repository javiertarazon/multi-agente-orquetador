# Agent Harness profesional

El harness es la frontera de ejecución entre el supervisor y Kilo, Cline,
Hermes o el executor de pruebas. Cada tarea pasa por este ciclo:

```text
contrato -> políticas -> executor -> captura normalizada -> validación -> persistencia
```

Actualmente centraliza:

- validación de timeout y executor;
- captura de excepciones para no dejar tareas en `running`;
- truncado de stdout/stderr y resumen;
- resultado normalizado con estado y código de salida;
- un punto único para añadir heartbeat, métricas, coste, cancelación y sandbox.

El harness no reemplaza el MCP ni el supervisor. Los complementa: OpenCode
planifica mediante MCP, el supervisor agenda y el harness protege cada
ejecución individual.

Para producción, el siguiente nivel puede añadir un backend de eventos,
heartbeats durante operaciones largas, presupuesto por plan y políticas
distintas para tareas de código, revisión y despliegue.
