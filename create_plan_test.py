import asyncio
import json
from orchestrator.interfaces.mcp.server import mcp

async def test():
    plan_data = {
        'plan': 'Crear sistema de rentabilidad >70% win rate para juego-pollo (3 huesos, 3 posiciones seguras)',
        'tasks': [
            {
                'prompt': 'Analizar estado actual del proyecto juego-pollo: leer README, configs, codigo ML, simulador, patrones',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto prueba/juego-pollo',
                'validation_commands': [['npx', 'tsx', 'verificar-sistema.ts']],
                'depends_on': []
            },
            {
                'prompt': 'Fase 1: Optimizar modelo ML (reinforcement-learning-rentable.ts) - epsilon 0.05, LR 0.20, fix DISCOUNT_FACTOR, peso adaptativo 40%',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto prueba/juego-pollo',
                'validation_commands': [['npx', 'tsx', 'analisis/enfrentamiento-asesor-vs-simulador.ts', '200', '3']],
                'depends_on': [0]
            },
            {
                'prompt': 'Fase 2: Mejorar deteccion patrones (adaptive-pattern-analyzer.ts + nuevo pattern-analyzer.ts) - ventana 20, clusters 5x5, Markov orden 2',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto prueba/juego-pollo',
                'validation_commands': [['npx', 'tsx', 'analisis/analyze-deep-patterns.ts', '20']],
                'depends_on': [1]
            },
            {
                'prompt': 'Fase 3: Ajustar motor simulacion (simulate/route.ts) - target 3, comportamiento rentable, 5000 partidas + re-entrenar',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto prueba/juego-pollo',
                'validation_commands': [['curl', '-X', 'POST', 'http://localhost:3000/api/chicken/simulate', '-H', 'Content-Type: application/json', '-d', '{"count":5000,"boneCount":3,"targetPositions":3,"useRealisticPatterns":true}']],
                'depends_on': [2]
            },
            {
                'prompt': 'Fase 4: Implementar gestion riesgo (ml-common.ts, simulator.ts) - Kelly sizing, trailing stop, session limits, Sharpe/Drawdown',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto prueba/juego-pollo',
                'validation_commands': [['npx', 'tsx', 'analisis/backtest-risk.ts', '1000']],
                'depends_on': [3]
            },
            {
                'prompt': 'Fase 5: Validacion estadistica final - 1000 partidas backtest, Chi-cuadrado, walk-forward, IC 95%',
                'executor': 'simulated',
                'workspace': 'D:/datos jt7/proyectos/proyecto prueba/juego-pollo',
                'validation_commands': [['npx', 'tsx', 'analisis/enfrentamiento-asesor-vs-simulador.ts', '1000', '3']],
                'depends_on': [4]
            }
        ],
        'workspace': 'D:/datos jt7/proyectos/proyecto prueba/juego-pollo',
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

asyncio.run(test())