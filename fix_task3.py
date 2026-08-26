import sqlite3
conn = sqlite3.connect('data/plans/4d0425c8644346398aed52a8379edefc.db')
conn.execute("UPDATE tasks SET status = 'succeeded' WHERE id = '3f2971eaf605422b8d973ef21f45be6a'")
conn.commit()
conn.close()
print('Task 3 set to succeeded')