import sqlite3

conn = sqlite3.connect("health.db")
cur = conn.cursor()

# 1. 사용자 넣기
cur.execute(
    "INSERT INTO users (name, birth_year, gender) VALUES (?, ?, ?)",
    ("이순자", 1958, "여")
)
user_id = cur.lastrowid
print("생성된 사용자 id:", user_id)

# 2. 그 사용자의 기록 넣기
cur.execute(
    """INSERT INTO records
       (user_id, date, weight, height, systolic, diastolic, blood_sugar, bmi, bmi_category)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (user_id, "2026-07-21", 68.0, 160.0, 120, 80, 95, 26.6, "비만")
)
record_id = cur.lastrowid
print("생성된 기록 id:", record_id)

# 3. 그 기록의 경고 넣기
cur.execute(
    "INSERT INTO warnings (record_id, message) VALUES (?, ?)",
    (record_id, "비만 상태입니다. 체중 관리가 필요합니다.")
)

conn.commit()

# 4. 꺼내보기
print("\n--- 사용자 목록 ---")
cur.execute("SELECT * FROM users")
for row in cur.fetchall():
    print(row)

print("\n--- 이순자의 기록 ---")
cur.execute("SELECT id, date, weight, bmi FROM records WHERE user_id = ?", (user_id,))
for row in cur.fetchall():
    print(row)

conn.close()