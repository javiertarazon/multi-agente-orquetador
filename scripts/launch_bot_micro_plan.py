from orchestrator.interfaces.mcp.server import create_plan, execute_plan

workspace = r"d:\datos jt7\proyectos\agentes_autonomos\trade bot\bot-trader-orquestado"
paths = [workspace + r"\src\**", workspace + r"\tests\**", workspace + r"\README.md"]
tasks = [
    {
        "prompt": "Solo analiza el bot-trader-orquestado y crea un archivo DATA_PIPELINE_PLAN.md en su raiz. Define una fuente publica de OHLCV historico, simbolo, timeframe, periodo, esquema CSV y reglas anti-lookahead. No modifiques codigo ni descargues datos.",
        "executor": "kilo", "workspace": workspace, "allowed_paths": [workspace + r"\DATA_PIPELINE_PLAN.md"],
        "validation_commands": [["python", "-c", "from pathlib import Path; assert Path('DATA_PIPELINE_PLAN.md').exists()"]],
        "timeout_seconds": 180, "max_retries": 1, "requires_review": True, "reviewer": "copilot"
    },
    {
        "prompt": "Implementa solo un loader historico CSV en src/bot_trader_orquestado/historical_data.py. Debe leer timestamp, open, high, low, close, volume, ordenar por timestamp y rechazar filas invalidas. No cambies otros archivos.",
        "executor": "kilo", "workspace": workspace, "allowed_paths": [workspace + r"\src\bot_trader_orquestado\historical_data.py"],
        "validation_commands": [["python", "-m", "py_compile", "src/bot_trader_orquestado/historical_data.py"]],
        "depends_on": [0], "timeout_seconds": 180, "max_retries": 1, "requires_review": True, "reviewer": "copilot"
    },
    {
        "prompt": "Crea únicamente tests/test_historical_data.py para validar el loader CSV: columnas requeridas, orden temporal y rechazo de precios invalidos. Ejecuta pytest de ese archivo y no modifiques produccion.",
        "executor": "cline", "workspace": workspace, "allowed_paths": [workspace + r"\tests\test_historical_data.py"],
        "validation_commands": [["python", "-m", "pytest", "tests/test_historical_data.py", "-q"]],
        "depends_on": [1], "timeout_seconds": 180, "max_retries": 1, "requires_review": True, "reviewer": "copilot"
    },
    {
        "prompt": "Revisa solo DATA_PIPELINE_PLAN.md, historical_data.py y test_historical_data.py. Ejecuta sus pruebas, comprueba que no hay lookahead ni datos sinteticos usados como evidencia y crea HISTORICAL_DATA_REVIEW.md con PASS/FAIL y hallazgos.",
        "executor": "cline", "workspace": workspace, "allowed_paths": [workspace + r"\HISTORICAL_DATA_REVIEW.md"],
        "validation_commands": [["python", "-m", "pytest", "tests/test_historical_data.py", "-q"]],
        "depends_on": [2], "timeout_seconds": 180, "max_retries": 1, "requires_review": True, "reviewer": "copilot"
    },
]
plan = create_plan("Bot trader microtareas: pipeline historico", tasks, workspace=workspace, auto_execute=False, target_return=0.55, max_drawdown=0.20, max_iterations=5)
print(plan)
print(execute_plan(plan["task_ids"], approved_by="copilot"))
