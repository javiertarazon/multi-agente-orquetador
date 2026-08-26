import sys, sqlite3, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
conn = sqlite3.connect(r'D:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado\data\plans\d5bd6d2cd138494c947e6b63abccebff.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(tasks)').fetchall()]
print('Columnas:', cols)
row = conn.execute("SELECT id, result FROM tasks WHERE id LIKE '0d4e7e31%'").fetchone()
if row and row[1]:
    res = json.loads(row[1])
    print(f'\nT2 status={res.get("status")} exit={res.get("exit_code")}')
    print(f'summary: {str(res.get("summary",""))[:300]}')
    print(f'stderr: {str(res.get("stderr",""))[:300]}')
    vals = res.get('validations') or []
    for v in vals:
        print(f'validacion {v["command"]} exit={v["exit_code"]}')
        print(f'  output: {str(v.get("output",""))[:200]}')
# Intentos de la tarea
try:
    atts = conn.execute("SELECT payload FROM task_attempts WHERE task_id LIKE '0d4e7e31%' ORDER BY rowid DESC LIMIT 2").fetchall()
    for a in atts:
        d = json.loads(a[0])
        print(f"\nINTENTO #{d.get('attempt_number')}: executor={d.get('executor')} error_cat={d.get('error_category')}")
        print(f"  resultado: {str(d.get('result',''))[:250] if d.get('result') else 'pendiente'}")
except Exception as e:
    print(f'(sin intentos: {e})')
conn.close()