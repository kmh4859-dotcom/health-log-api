import sqlite3
conn = sqlite3.connect("health.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    birth_year INTEGER,
    gender TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    weight REAL NOT NULL,
    height REAL NOT NULL,
    systolic INTEGER NOT NULL,
    diastolic INTEGER NOT NULL,
    blood_sugar INTEGER NOT NULL,
    steps INTEGER DEFAULT 0,
    sleep_hours REAL DEFAULT 0,
    memo TEXT DEFAULT '',
    bmi REAL,
    bmi_category TEXT,
    bp_category TEXT,
    sugar_category TEXT,
    steps_category TEXT,
    sleep_category TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    goal_type TEXT NOT NULL,
    target_value REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    FOREIGN KEY (record_id) REFERENCES records(id)
)
""")


cur.execute("""
CREATE TABLE IF NOT EXISTS guardianships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guardian_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    relation TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (guardian_id, patient_id),
    FOREIGN KEY (guardian_id) REFERENCES users(id),
    FOREIGN KEY (patient_id) REFERENCES users(id)
)
""")


conn.commit()
conn.close()
print("데이터베이스 생성 완료!")