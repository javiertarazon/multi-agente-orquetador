import sys, sqlite3, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DB = r'D:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado\data\plans\d5bd6d2cd138494c947e6b63abccebff.db'
NOMBRES = {1:'Setup: npm install',2:'FASE 0: Verificar baseline',3:'FASE 1: Optimizar ML',4:'FASE 2: Patrones',5:'FASE 3: Simulacion',6:'FASE 4: Riesgo',7:'FASE 5: Validacion'}
ICONOS = {'succeeded':'[ OK ]','failed':'[FALLO]','queued':'[ESPERA]','running':'[ EJEC ]','retry_wait':'[RETRY]','awaiting_approval':'[REVIS]'}

def mostrar():
    conn = sqlite3.connect(DB)
    rows = conn.execute('SELECT status, priority FROM tasks ORDER BY priority, rowid').fetchall()
    conn.close()
    total = len(rows)
    ok = sum(1 for r in rows if r[0]=='succeeded')
    fallos = sum(1 for r in rows if r[0]=='failed')
    ejec = sum(1 for r in rows if r[0]=='running')
    done = ok + fallos
    barra = '#' * int(ok/total*30) + '.' * (30 - int(ok/total*30))
    print(f'AVANCE [{barra}] {ok*100//total}% | OK:{ok} FALLO:{fallos} EJECUTANDO:{ejec} PENDIENTE:{total-done}')
    for st, pri in rows:
        print(f'   {ICONOS.get(st, st)} {NOMBRES.get(pri, f"T{pri}")}')
    return ok, total

if __name__ == '__main__':
    ciclos = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    espera = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    for i in range(ciclos):
        print(f'--- MONITOREO {i+1}/{ciclos} ---')
        ok, total = mostrar()
        if ok >= total:
            print('>>> PLAN COMPLETADO <<<')
            break
        if i < ciclos - 1:
            time.sleep(espera)
            print()