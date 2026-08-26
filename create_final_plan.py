import asyncio
import json
from orchestrator.interfaces.mcp.server import mcp

async def create_plan():
    plan_data = {
        'plan': 'Crear sistema de rentabilidad >70% win rate para juego-pollo (3 huesos, 3 posiciones seguras)',
        'tasks': [
            {
                'prompt': 'Analizar estado actual del proyecto juego-pollo: leer configs, código ML, simulador, patrones. Verificar baseline actual con npx tsx verificar-sistema.ts',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto  prueba/juego-pollo',
                'validation_commands': [['cmd', '/c', 'npx', 'tsx', 'verificar-sistema.ts']],
                'depends_on': []
            },
            {
                'prompt': 'FASE 1: Optimizar modelo ML - Editar src/lib/ml/reinforcement-learning-rentable.ts: MIN_EPSILON 0.05, LEARNING_RATE 0.20, fix DISCOUNT_FACTOR en linea 407, peso adaptativo 40%, epsilon dinamico, filtrar top 3 posiciones ultra seguras, bonus secuencia ganadora',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto  prueba/juego-pollo',
                'validation_commands': [['cmd', '/c', 'npx', 'tsx', 'analisis/enfrentamiento-asesor-vs-simulador.ts', '200', '3']],
                'depends_on': [0]
            },
            {
                'prompt': 'FASE 2: Mejorar deteccion patrones - Editar src/lib/ml/adaptive-pattern-analyzer.ts: ventana 20 partidas, clusters espaciales 5x5, analisis diagonales/esquinas. Crear src/lib/ml/pattern-analyzer.ts portando logica de ml-python/pattern_analyzer.py (Markov orden 2, score confianza, cache invalidation)',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto  prueba/juego-pollo',
                'validation_commands': [['cmd', '/c', 'npx', 'tsx', 'analisis/analyze-deep-patterns.ts', '20']],
                'depends_on': [1]
            },
            {
                'prompt': 'FASE 3: Ajustar motor simulacion - Editar src/app/api/chicken/simulate/route.ts: targetPositions=3 default, cashOutBehavior objetivo 3, comportamiento rentable. Generar 5000 partidas simuladas y re-entrenar asesor',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto  prueba/juego-pollo',
                'validation_commands': [['cmd', '/c', 'curl', '-X', 'POST', 'http://localhost:3000/api/chicken/simulate', '-H', 'Content-Type: application/json', '-d', '{"count":5000,"boneCount":3,"targetPositions":3,"useRealisticPatterns":true}']],
                'depends_on': [2]
            },
            {
                'prompt': 'FASE 4: Implementar gestion riesgo - Crear/editar src/lib/ml/ml-common.ts (Kelly Criterion, stats compartidas) y src/lib/roi/simulator.ts (backtesting 1000 juegos, Sharpe, Drawdown, Profit Factor). Stop-loss 3 derrotas, trailing stop, session limits 50 partidas',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto  prueba/juego-pollo',
                'validation_commands': [['cmd', '/c', 'npx', 'tsx', 'analisis/backtest-risk.ts', '1000']],
                'depends_on': [3]
            },
            {
                'prompt': 'FASE 5: Validacion estadistica final - Ejecutar 1000 partidas backtest, Chi-cuadrado, test binomial IC 95%, walk-forward 70/30, validar 3 posiciones seguras >80% casos. Documentar CONFIG_PRODUCCION.json',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto  prueba/juego-pollo',
                'validation_commands': [['cmd', '/c', 'npx', 'tsx', 'analisis/enfrentamiento-asesor-vs-simulador.ts', '1000', '3']],
                'depends_on': [4]
            }
        ],
        'workspace': 'D:/datos jt7/proyectos/proyecto  prueba/juego-pollo',
        'target_return': 0.70,
        'max_drawdown': 0.15,
        'max_iterations': 3
    }
    
    result = await mcp.call_tool('create_plan', plan_data)
    print('Create Plan Result:')
    for item in result:
        if hasattr(item, 'text'):
            print(item.text)
        else:
            print(json.dumps(item, indent=2))

asyncio.run(create_plan())