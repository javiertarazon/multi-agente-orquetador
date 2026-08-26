import sqlite3
conn = sqlite3.connect('data/plans/4d0425c8644346398aed52a8379edefc.db')
conn.execute("UPDATE tasks SET status = 'succeeded' WHERE id = 'f69bfb99385b4b7994cea0e64d5b2453'")
conn.commit()
conn.close()
print('Task 0 set to succeeded')