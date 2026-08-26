import sys
import traceback
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from orchestrator.adapters.storage import TaskStore
from orchestrator.adapters.executors import executor_for

DB = r'D:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado\data\plans\d5bd6d2cd138494c947e6b63abccebff.db'
store = TaskStore(DB)
task = store.get('0d4e7e31f85c49eea0920eb532712c89')
print(f'Ejecutor: {task.executor.value}')
print(f'Prompt: {task.prompt[:100]}')

executor = executor_for(task.executor)
try:
    result = executor.run(task)
    print(f'RESULTADO: status={result.status.value} exit={result.exit_code}')
    print(f'summary: {str(result.summary)[:200]}')
except Exception:
    print('EXCEPCION CAPTURADA:')
    traceback.print_exc()