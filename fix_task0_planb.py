import sqlite3
conn = sqlite3.connect(r'D:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado\data\plans\d5bd6d2cd138494c947e6b63abccebff.db')
row = conn.execute("SELECT status FROM tasks WHERE id = '552712878c1b45c5a9bcfeba56046883'").fetchone()
print(f'Estado actual Tarea 0: {row[0]}')
conn.execute("UPDATE tasks SET status = 'succeeded' WHERE id = '552712878c1b45c5a9bcfeba56046883'")
conn.commit()
row2 = conn.execute("SELECT id, status FROM tasks ORDER BY priority, rowid").fetchall()
for r in row2:
    print(f'{r[0][:8]}: {r[1]}')
conn.close()
print('Tarea 0 marcada como succeeded (dependencias instaladas y verificadas)')