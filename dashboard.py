import sys, sqlite3, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
conn = sqlite3.connect(r'D:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado\data\plans\d5bd6d2cd138494c947e6b63abccebff.db')
rows = conn.execute('SELECT id, status, priority FROM tasks ORDER BY priority, rowid').fetchall()
total = len(rows)
done = sum(1 for r in rows if r[1] in ('succeeded','failed','rejected','cancelled'))
ok = sum(1 for r in rows if r[1] == 'succeeded')
print(f'=== TABLERO DE PROGRESO: {done}/{total} terminadas ({done*100//total}%) | exitosas: {ok} ===')
print()
nombres = {2:'FASE 0: Verificar baseline',3:'FASE 1: Optimizar ML',4:'FASE 2: Patrones',5:'FASE 3: Simulacion',6:'FASE 4: Riesgo',7:'FASE 5: Validacion'}
iconos = {'succeeded':'OK ','failed':'FALLO','queued':'ESPERA','running':'EJEC ','retry_wait':'RETRY'}
for r in rows:
    nom = nombres.get(r[2], 'Setup: npm install')
    print(f'  [{iconos.get(r[1], r[1]):>6}] T{r[2]} {nom}')
print()
# Ultimo resultado con detalle
row = conn.execute("SELECT id, result FROM tasks WHERE result IS NOT NULL ORDER BY updated_at DESC LIMIT 1").fetchone()
if row and row[1]:
    res = json.loads(row[1])
    print(f'ULTIMO RESULTADO ({row[0][:8]}): status={res.get("status")}')
    print(f'  summary: {str(res.get("summary",""))[:200]}')
    vals = res.get('validations') or []
    for v in vals[:2]:
        print(f'  validacion exit={v["exit_code"]}: {str(v.get("output",""))[:150]}')
conn.close()