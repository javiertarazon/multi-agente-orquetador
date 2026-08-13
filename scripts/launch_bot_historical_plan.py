from orchestrator.interfaces.mcp.server import create_plan, execute_plan

workspace = r"d:\datos jt7\proyectos\agentes_autonomos\trade bot\bot-trader-orquestado"
tasks = [
    {
        "prompt": "Preparar un pipeline de datos OHLCV historicos reales para bot-trader-orquestado. Usa una fuente publica reproducible o CSV documentado, conserva timestamps, evita lookahead y no uses datos sinteticos como evidencia. Anade loader, configuracion y tests de calidad de datos.",
        "executor": "kilo",
        "priority": 1,
        "workspace": workspace,
        "allowed_paths": [workspace + r"\src\**", workspace + r"\tests\**", workspace + r"\README.md"],
        "validation_commands": [["python", "-m", "pytest", "-q"]],
        "max_retries": 2,
        "requires_review": True,
        "reviewer": "copilot",
    },
    {
        "prompt": "Implementar un backtest realista sobre el dataset historico preparado: comision, spread, slippage, sizing por riesgo, stop loss, take profit, equity curve, retorno neto, max drawdown, Sharpe y profit factor. Ejecuta validacion temporal y deja un reporte reproducible. No habilites live trading.",
        "executor": "cline",
        "priority": 2,
        "workspace": workspace,
        "allowed_paths": [workspace + r"\src\**", workspace + r"\tests\**", workspace + r"\README.md"],
        "validation_commands": [["python", "-m", "pytest", "-q"]],
        "max_retries": 2,
        "depends_on": [0],
        "requires_review": True,
        "reviewer": "copilot",
    },
    {
        "prompt": "Evaluar el backtest historico fuera de muestra y optimizar estrategia/riesgo sin sobreajuste. La aceptacion exige retorno neto >= 0.55 y max drawdown <= 0.20 con costes incluidos. Si no cumple, documenta metricas y cambios para la siguiente iteracion; nunca declares rentabilidad con datos sinteticos.",
        "executor": "kilo",
        "priority": 3,
        "workspace": workspace,
        "allowed_paths": [workspace + r"\src\**", workspace + r"\tests\**", workspace + r"\README.md"],
        "validation_commands": [["python", "-m", "pytest", "-q"]],
        "max_retries": 3,
        "depends_on": [1],
        "requires_review": True,
        "reviewer": "copilot",
    },
    {
        "prompt": "Revisar con Cline el resultado final del backtest historico, comprobar retorno >=55%, drawdown <=20%, costes, leakage, robustez y evidencia fuera de muestra. Emitir informe final y marcar incumplimiento si las metricas no alcanzan los umbrales.",
        "executor": "cline",
        "priority": 4,
        "workspace": workspace,
        "allowed_paths": [workspace + r"\**"],
        "validation_commands": [["python", "-m", "pytest", "-q"]],
        "max_retries": 2,
        "depends_on": [2],
        "requires_review": True,
        "reviewer": "copilot",
    },
]

plan = create_plan(
    "Bot trader: datos historicos reales, backtest realista y loop de mejora",
    tasks,
    workspace=workspace,
    auto_execute=False,
    target_return=0.55,
    max_drawdown=0.20,
    max_iterations=5,
)
print(plan)
print(execute_plan(plan["task_ids"], approved_by="copilot"))
