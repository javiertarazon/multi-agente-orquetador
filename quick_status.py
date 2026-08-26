import sqlite3
conn = sqlite3.connect(r'D:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado\data\plans\d5bd6d2cd138494c947e6b63abccebff.db')
rows = conn.execute("SELECT id, status FROM tasks ORDER BY priority, rowid").fetchall()
for r in rows:
    print(f'{r[0][:8]}: {r[1]}')
conn.close()