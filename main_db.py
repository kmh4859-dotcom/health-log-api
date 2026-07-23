import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi. responses import FileResponse
from pydantic import BaseModel
from datetime import datetime, timedelta

app = FastAPI(title="마이 헬스 로그 API (DB)", version="2.0")

DB_FILE = "health.db"


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


class UserIn(BaseModel):
    name: str
    birth_year: int = 0
    gender: str = ""


@app.get("/")
def read_root():
    return FileResponse("index_db.html")


@app.post("/users")
def create_user(user: UserIn):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (name, birth_year, gender) VALUES (?, ?, ?)",
            (user.name, user.birth_year, user.gender)
        )
        conn.commit()
        new_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="이미 존재하는 사용자입니다")
    conn.close()
    return {"id": new_id, "name": user.name}


@app.get("/users")
def get_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users")
    rows = cur.fetchall()
    conn.close()
    return {
        "count": len(rows),
        "users": [dict(row) for row in rows]
    }


def calculate_bmi(weight, height):
    height_m = height / 100
    return round(weight / (height_m * height_m), 1)


def classify_bmi(bmi):
    if bmi < 18.5:
        return "저체중"
    elif bmi < 23:
        return "정상"
    elif bmi < 25:
        return "과체중"
    else:
        return "비만"


def classify_bp(systolic, diastolic):
    if systolic >= 140 or diastolic >= 90:
        return "고혈압"
    elif systolic >= 120 or diastolic >= 80:
        return "주의"
    else:
        return "정상"


def classify_sugar(blood_sugar):
    if blood_sugar < 100:
        return "정상"
    elif blood_sugar < 126:
        return "공복혈당장애"
    else:
        return "당뇨 의심"


def classify_steps(steps):
    if steps < 5000:
        return "부족"
    elif steps < 10000:
        return "적정"
    else:
        return "우수"


def classify_sleep(sleep_hours):
    if sleep_hours < 6:
        return "부족"
    elif sleep_hours <= 9:
        return "적정"
    else:
        return "과다"


def make_warnings(bmi_cat, bp_cat, sugar_cat):
    result = []
    if bmi_cat == "비만":
        result.append("비만 상태입니다. 체중 관리가 필요합니다.")
    if bp_cat == "고혈압":
        result.append("고혈압입니다. 혈압 관리가 필요합니다.")
    if sugar_cat == "당뇨 의심":
        result.append("당뇨가 의심됩니다. 검사를 권장합니다.")
    return result


class RecordIn(BaseModel):
    user_id: int
    date: str
    weight: float
    height: float
    systolic: int
    diastolic: int
    blood_sugar: int
    steps: int = 0
    sleep_hours: float = 0.0
    memo: str = ""


@app.post("/records")
def create_record(record: RecordIn):
    bmi = calculate_bmi(record.weight, record.height)
    bmi_cat = classify_bmi(bmi)
    bp_cat = classify_bp(record.systolic, record.diastolic)
    sugar_cat = classify_sugar(record.blood_sugar)
    steps_cat = classify_steps(record.steps)
    sleep_cat = classify_sleep(record.sleep_hours)
    warning_list = make_warnings(bmi_cat, bp_cat, sugar_cat)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE id = ?", (record.user_id,))
    if cur.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    cur.execute("""
        INSERT INTO records
        (user_id, date, weight, height, systolic, diastolic, blood_sugar,
         steps, sleep_hours, memo, bmi, bmi_category, bp_category,
         sugar_category, steps_category, sleep_category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (record.user_id, record.date, record.weight, record.height,
          record.systolic, record.diastolic, record.blood_sugar,
          record.steps, record.sleep_hours, record.memo,
          bmi, bmi_cat, bp_cat, sugar_cat, steps_cat, sleep_cat))

    record_id = cur.lastrowid

    for message in warning_list:
        cur.execute(
            "INSERT INTO warnings (record_id, message) VALUES (?, ?)",
            (record_id, message)
        )

    conn.commit()
    conn.close()

    return {
        "id": record_id,
        "user_id": record.user_id,
        "date": record.date,
        "weight": record.weight,
        "bmi": bmi,
        "bmi_category": bmi_cat,
        "bp_category": bp_cat,
        "sugar_category": sugar_cat,
        "steps_category": steps_cat,
        "sleep_category": sleep_cat,
        "warnings": warning_list
    }


def get_warnings(cur, record_id):
    cur.execute("SELECT message FROM warnings WHERE record_id = ?", (record_id,))
    return [row["message"] for row in cur.fetchall()]


@app.get("/records")
def get_records(user_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT records.*, users.name AS user_name
        FROM records
        JOIN users ON records.user_id = users.id
        WHERE records.user_id = ?
        ORDER BY records.date DESC        
    """, (user_id,))
    rows = cur.fetchall()

    result = []
    for row in rows:
        record = dict(row)
        record["warnings"] = get_warnings(cur, row["id"])
        result.append(record)

    conn.close()
    return {"count": len(result), "records": result}


@app.get("/records/{record_id}")
def get_record(record_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT records.*, users.name AS user_name
        FROM records
        JOIN users ON records.user_id = users.id
        WHERE records.id = ?
    """, (record_id,))
    row = cur.fetchone()

    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")

    record = dict(row)
    record["warnings"] = get_warnings(cur, record_id)

    conn.close()
    return record


@app.put("/records/{record_id}")
def update_record(record_id: int, record: RecordIn):
    bmi = calculate_bmi(record.weight, record.height)
    bmi_cat = classify_bmi(bmi)
    bp_cat = classify_bp(record.systolic, record.diastolic)
    sugar_cat = classify_sugar(record.blood_sugar)
    steps_cat = classify_steps(record.steps)
    sleep_cat = classify_sleep(record.sleep_hours)
    warning_list = make_warnings(bmi_cat, bp_cat, sugar_cat)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM records WHERE id = ?", (record_id,))
    if cur.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")

    cur.execute("""
        UPDATE records SET
        user_id = ?, date = ?, weight = ?, height = ?, systolic = ?,
        diastolic = ?, blood_sugar = ?, steps = ?, sleep_hours = ?, memo = ?,
        bmi = ?, bmi_category = ?, bp_category = ?, sugar_category = ?,
        steps_category = ?, sleep_category = ?
        WHERE id = ?
    """, (record.user_id, record.date, record.weight, record.height,
          record.systolic, record.diastolic, record.blood_sugar,
          record.steps, record.sleep_hours, record.memo,
          bmi, bmi_cat, bp_cat, sugar_cat, steps_cat, sleep_cat, record_id))

    cur.execute("DELETE FROM warnings WHERE record_id = ?", (record_id,))
    for message in warning_list:
        cur.execute(
            "INSERT INTO warnings (record_id, message) VALUES (?, ?)",
            (record_id, message)
        )

    conn.commit()
    conn.close()
    return {"id": record_id, "bmi": bmi, "bmi_category": bmi_cat,
            "warnings": warning_list, "message": "수정되었습니다"}


@app.delete("/records/{record_id}")
def delete_record(record_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM records WHERE id = ?", (record_id,))
    if cur.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")

    cur.execute("DELETE FROM warnings WHERE record_id = ?", (record_id,))
    cur.execute("DELETE FROM records WHERE id = ?", (record_id,))

    conn.commit()
    conn.close()
    return {"message": "삭제되었습니다"}


@app.get("/search")
def search_records(user_id: int, start: str, end: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT records.*, users.name AS user_name
        FROM records
        JOIN users ON records.user_id = users.id
        WHERE records.user_id = ? AND records.date BETWEEN ? AND ?
        ORDER BY records.date DESC
    """, (user_id, start, end))
    rows = cur.fetchall()

    result = []
    for row in rows:
        record = dict(row)
        record["warnings"] = get_warnings(cur, row["id"])
        result.append(record)

    conn.close()
    return {"count": len(result), "records": result}


@app.get("/stats")
def get_stats(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) AS count,
               ROUND(AVG(weight), 1) AS avg_weight,
               ROUND(AVG(bmi), 1) AS avg_bmi,
               MIN(weight) AS min_weight,
               MAX(weight) AS max_weight
        FROM records WHERE user_id = ?
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if row["count"] == 0:
        return {"message": "기록이 없습니다"}
    return dict(row)


class GoalIn(BaseModel):
    user_id: int
    goal_type: str
    target_value: float


@app.post("/goals")
def set_goal(goal: GoalIn):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE id = ?", (goal.user_id,))
    if cur.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    cur.execute(
        "DELETE FROM goals WHERE user_id = ? AND goal_type = ?",
        (goal.user_id, goal.goal_type)
    )
    cur.execute(
        "INSERT INTO goals (user_id, goal_type, target_value) VALUES (?, ?, ?)",
        (goal.user_id, goal.goal_type, goal.target_value)
    )

    conn.commit()
    conn.close()
    return {"user_id": goal.user_id, "goal_type": goal.goal_type,
            "target_value": goal.target_value}


@app.get("/goals")
def get_goals(user_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT goal_type, target_value FROM goals WHERE user_id = ?",
        (user_id,)
    )
    goals = [dict(row) for row in cur.fetchall()]

    if len(goals) == 0:
        conn.close()
        return {"message": "설정된 목표가 없습니다"}

    cur.execute(
        "SELECT weight FROM records WHERE user_id = ? ORDER BY date DESC LIMIT 1",
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()

    result = {"user_id": user_id, "goals": goals}
    if row is not None:
        current = row["weight"]
        result["current_weight"] = current
        for g in goals:
            if g["goal_type"] == "weight":
                result["remaining"] = round(current - g["target_value"], 1)

    return result


@app.get("/weekly-report")
def weekly_report(user_id: int):
    today = datetime.now()
    week1_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    week2_start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT ROUND(AVG(weight), 1) AS avg_weight, COUNT(*) AS count
        FROM records
        WHERE user_id = ? AND date >= ? AND date <= ?
    """, (user_id, week1_start, today_str))
    this_week = cur.fetchone()

    cur.execute("""
        SELECT ROUND(AVG(weight), 1) AS avg_weight, COUNT(*) AS count
        FROM records
        WHERE user_id = ? AND date >= ? AND date < ?
    """, (user_id, week2_start, week1_start))
    last_week = cur.fetchone()

    conn.close()

    change = None
    if this_week["avg_weight"] is not None and last_week["avg_weight"] is not None:
        change = round(this_week["avg_weight"] - last_week["avg_weight"], 1)

    return {
        "this_week": {"avg_weight": this_week["avg_weight"], "count": this_week["count"]},
        "last_week": {"avg_weight": last_week["avg_weight"], "count": last_week["count"]},
        "change": change
    }