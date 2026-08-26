import sys, sqlite3, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DB = r'D:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado\data\plans\d5bd6d2cd138494c947e6b63abccebff.db'
conn = sqlite3.connect(DB)
# T1: estado + resultado coherentes como succeeded
row = conn.execute("SELECT payload, result FROM tasks WHERE id LIKE '55271287%'").fetchone()
payload = json.loads(row[0])
payload['status'] = 'succeeded'
res = json.loads(row[1]) if row[1] else {}
res['status'] = 'succeeded'
res['summary'] = 'Dependencias npm instaladas y verificadas manualmente (node_modules + tsx presentes)'
conn.execute("UPDATE tasks SET status='succeeded', payload=?, result=? WHERE id LIKE '55271287%'",
             (json.dumps(payload), json.dumps(res)))
conn.commit()
# Verificar
r = conn.execute("SELECT status, result FROM tasks WHERE id LIKE '55271287%'").fetchone()
d = json.loads(r[1])
print(f"T1: status={r[0]}, result.status={d['status']}")
rows = conn.execute("SELECT priority, status FROM tasks ORDER BY priority").fetchall()
for p, s in rows:
    print(f'T{p}: {s}')
conn.close()