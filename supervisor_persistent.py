import sys
import time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from orchestrator.adapters.storage import TaskStore
from orchestrator.application.worker import Worker

DB = r'D:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado\data\plans\d5bd6d2cd138494c947e6b63abccebff.db'
TERMINAL = {'succeeded', 'failed', 'rejected', 'cancelled'}

def main():
    store = TaskStore(DB)
    worker = Worker(store)
    print(f'SUPERVISOR PERSISTENTE iniciado sobre {DB}', flush=True)
    idle_cycles = 0
    while True:
        # Reencolar tareas stuck en running sin heartbeat reciente (>10 min)
        try:
            store.recover_stale_running(max_age_seconds=600)
        except Exception as e:
            print(f'recover_stale_running error: {e}', flush=True)
        tasks = store.list(limit=100)
        if not tasks:
            print('Sin tareas. Saliendo.', flush=True)
            return
        if all(t.status.value in TERMINAL for t in tasks):
            estados = [t.status.value for t in tasks]
            print(f'PLAN COMPLETADO. Estados finales: {estados}', flush=True)
            return
        stats = worker.run_parallel(max_workers=1)
        print(f'Ciclo: processed={stats.processed} ok={stats.succeeded} fail={stats.failed}', flush=True)
        time.sleep(2)

if __name__ == '__main__':
    main()