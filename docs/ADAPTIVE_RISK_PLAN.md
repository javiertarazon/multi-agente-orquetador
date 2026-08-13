# Plan: bot adaptativo y riesgo conservador

Plan MCP: `230c39db2a674f17b03d57d9d5521924`
Base aislada: `data/plans/230c39db2a674f17b03d57d9d5521924.db`
Workspace objetivo: `bot-trader-orquestado`

## Objetivo

Mejorar la robustez del bot ante cambios de régimen del mercado mediante detección de tendencia/rango/volatilidad, sizing conservador, límites de pérdida y trailing stop dinámico. El objetivo de retorno del plan es `0.55` y el drawdown máximo es `0.20`, pero son criterios de evaluación, no una garantía de rentabilidad.

## Secuencia MCP

1. Auditoría sin cambios: `MARKET_ADAPTIVE_AUDIT.md`.
2. Detector de régimen sin lookahead.
3. Pruebas del detector.
4. Risk manager adaptativo y trailing stop ATR.
5. Pruebas de riesgo y kill switches.
6. Integración en backtest, sin live trading.
7. Backtest con datos históricos reales, costes y muestra fuera de tiempo.
8. Revisión independiente de evidencia, leakage y robustez.

## Controles de riesgo obligatorios

- Riesgo máximo por operación.
- Límite de pérdida diaria.
- Límite de drawdown global.
- Límite de pérdidas consecutivas.
- Reducción de exposición con volatilidad alta.
- Kill switch al superar drawdown o pérdidas.
- Trailing stop que solo se mueve a favor y respeta distancia mínima.
- Prohibición de aumentar riesgo para recuperar pérdidas.
- No activar live trading durante este plan.

## Evidencia de aceptación

El JSON de backtest debe declarar `data_is_real`, `data_source`, `costs_included`, `out_of_sample`, `total_return`, `max_drawdown`, `sharpe` y `profit_factor`. Si faltan datos reales, costes o validación fuera de muestra, el resultado se rechaza aunque el retorno sea alto.

## Ejecución

El plan se creó con `auto_execute=false`. Tras la aprobación explícita de delegación, se ejecuta mediante MCP con `execute_plan` usando los ocho `task_ids` devueltos por `scripts/launch_bot_adaptive_risk_plan.py`.
