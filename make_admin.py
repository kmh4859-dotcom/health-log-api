import sqlite3

conn = sqlite3.connect("health.db")
cur = conn.cursor()
cur.execute("UPDATE users SET role = 'admin' WHERE name = ?", ("이순자",))
conn.commit()
conn.close()
print("관리자로 변경되었습니다")