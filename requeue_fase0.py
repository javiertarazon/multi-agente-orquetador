import sqlite3
conn = sqlite3.connect(r'D:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado\data\plans\d5bd6d2cd138494c947e6b63abccebff.db')
conn.execute("UPDATE tasks SET status = 'queued', result = NULL WHERE id = '0d4e7e31f85c49eea0920eb532712c89'")
conn.commit()
rows = conn.execute("SELECT id, status FROM tasks ORDER BY priority, rowid").fetchall()
for r in rows:
    print(f'{r[0][:8]}: {r[1]}')
conn.close()