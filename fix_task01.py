import sqlite3
conn = sqlite3.connect('data/plans/4d0425c8644346398aed52a8379edefc.db')
conn.execute("UPDATE tasks SET status = 'succeeded' WHERE id IN ('f69bfb99385b4b7994cea0e64d5b2453', 'b092372b530e4991af8160f2c84201aa')")
conn.commit()
conn.close()
print('Tasks 0 and 1 set to succeeded')