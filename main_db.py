import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi. responses import FileResponse
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

app = FastAPI(title="마이 헬스 로그 API (DB)", version="2.0")

DB_FILE = "health.db"


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


SECRET_KEY = "change-this-to-a-long-random-string"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 180

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def hash_password(password):
    return pwd_context.hash(password)


def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)


def create_token(user_id, name, role):
    expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "name": name, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": int(payload["sub"]), "name": payload["name"], "role": payload["role"]}
    except JWTError:
        raise HTTPException(status_code=401, detail="인증에 실패했습니다")


def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="관리자만 접근할 수 있습니다")
    return current_user


def get_record_or_403(cur, record_id, current_user):
    cur.execute("SELECT * FROM records WHERE id = ?", (record_id,))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
    if row["user_id"] != current_user["id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="이 기록에 접근할 권한이 없습니다")
    return row

    
class UserIn(BaseModel):
    name: str
    birth_year: int = 0
    gender: str = ""


@app.get("/")
def read_root():
    return FileResponse("index_db.html")


@app.get("/users")
def get_users(admin: dict = Depends(require_admin)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, role, birth_year, gender, created_at FROM users")
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
    weight: float = Field(..., ge=20, le=300, description="몸무게(kg)")
    height: float = Field(..., ge=50, le=250, description="키(cm)")
    systolic: int = Field(..., ge=50, le=250, description="수축기 혈압")
    diastolic: int = Field(..., ge=30, le=150, description="이완기 혈압")
    blood_sugar: int = Field(..., ge=20, le=600, description="공복 혈당")
    steps: int = Field(0, ge=0, le=100000, description="걸음 수")
    sleep_hours: float = Field(0.0, ge=0, le=24, description="수면 시간")
    memo: str = ""


@app.post("/records")
def create_record(record: RecordIn, current_user: dict = Depends(get_current_user)):
    record.user_id = current_user["id"]
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
def get_records(current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT records.*, users.name AS user_name
        FROM records
        JOIN users ON records.user_id = users.id
        WHERE records.user_id = ?
        ORDER BY records.date DESC        
    """, (current_user["id"],))
    rows = cur.fetchall()

    result = []
    for row in rows:
        record = dict(row)
        record["warnings"] = get_warnings(cur, row["id"])
        result.append(record)

    conn.close()
    return {"count": len(result), "records": result}


@app.get("/records/{record_id}")
def get_record(record_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    get_record_or_403(cur, record_id, current_user)

    cur.execute("""
        SELECT records.*, users.name AS user_name
        FROM records
        JOIN users ON records.user_id = users.id
        WHERE records.id = ?
    """, (record_id,))
    row = cur.fetchone()

    record = dict(row)
    record["warnings"] = get_warnings(cur, record_id)

    conn.close()
    return record

@app.put("/records/{record_id}")
def update_record(record_id: int, record: RecordIn, current_user: dict = Depends(get_current_user)):
    bmi = calculate_bmi(record.weight, record.height)
    bmi_cat = classify_bmi(bmi)
    bp_cat = classify_bp(record.systolic, record.diastolic)
    sugar_cat = classify_sugar(record.blood_sugar)
    steps_cat = classify_steps(record.steps)
    sleep_cat = classify_sleep(record.sleep_hours)
    warning_list = make_warnings(bmi_cat, bp_cat, sugar_cat)

    conn = get_conn()
    cur = conn.cursor()

    get_record_or_403(cur, record_id, current_user)
    record.user_id = current_user["id"]

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
def delete_record(record_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    get_record_or_403(cur, record_id, current_user)

    cur.execute("DELETE FROM warnings WHERE record_id = ?", (record_id,))
    cur.execute("DELETE FROM records WHERE id = ?", (record_id,))

    conn.commit()
    conn.close()
    return {"message": "삭제되었습니다"}


@app.get("/search")
def search_records(start: str, end: str, current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT records.*, users.name AS user_name
        FROM records
        JOIN users ON records.user_id = users.id
        WHERE records.user_id = ? AND records.date BETWEEN ? AND ?
        ORDER BY records.date DESC
    """, (current_user["id"], start, end))
    rows = cur.fetchall()

    result = []
    for row in rows:
        record = dict(row)
        record["warnings"] = get_warnings(cur, row["id"])
        result.append(record)

    conn.close()
    return {"count": len(result), "records": result}


@app.get("/stats")
def get_stats(current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) AS count,
               ROUND(AVG(weight), 1) AS avg_weight,
               ROUND(AVG(bmi), 1) AS avg_bmi,
               MIN(weight) AS min_weight,
               MAX(weight) AS max_weight
        FROM records WHERE user_id = ?
    """, (current_user["id"],))
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
def set_goal(goal: GoalIn, current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    user_id = current_user["id"]

    cur.execute(
        "DELETE FROM goals WHERE user_id = ? AND goal_type = ?",
        (user_id, goal.goal_type)
    )
    cur.execute(
        "INSERT INTO goals (user_id, goal_type, target_value) VALUES (?, ?, ?)",
        (user_id, goal.goal_type, goal.target_value)
    )

    conn.commit()
    conn.close()
    return {"user_id": user_id, "goal_type": goal.goal_type,
            "target_value": goal.target_value}


@app.get("/goals")
def get_goals(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
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
def weekly_report(current_user: dict = Depends(get_current_user)):
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
    """, (current_user["id"], week1_start, today_str))
    this_week = cur.fetchone()

    cur.execute("""
        SELECT ROUND(AVG(weight), 1) AS avg_weight, COUNT(*) AS count
        FROM records
        WHERE user_id = ? AND date >= ? AND date < ?
    """, (current_user["id"], week2_start, week1_start))
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


class GuardianshipIn(BaseModel):
    guardian_id: int
    patient_id: int
    relation: str = ""


@app.post("/guardianships")
def create_guardianship(g: GuardianshipIn, current_user: dict = Depends(get_current_user)):
    guardian_id = current_user["id"]

    if guardian_id == g.patient_id:
        raise HTTPException(status_code=400, detail="자기 자신을 보호자로 등록할 수 없습니다")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE id = ?", (g.patient_id,))
    if cur.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="존재하지 않는 사용자입니다")

    try:
        cur.execute(
            "INSERT INTO guardianships (guardian_id, patient_id, relation) VALUES (?, ?, ?)",
            (guardian_id, g.patient_id, g.relation)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="이미 등록된 관계입니다")

    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "guardian_id": guardian_id,
            "patient_id": g.patient_id, "relation": g.relation}


@app.get("/guardianships")
def get_my_patients(current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT guardianships.id, guardianships.patient_id,
               guardianships.relation, users.name AS patient_name
        FROM guardianships
        JOIN users ON guardianships.patient_id = users.id
        WHERE guardianships.guardian_id = ?
    """, (current_user["id"],))
    rows = cur.fetchall()
    conn.close()
    return {"count": len(rows), "patients": [dict(r) for r in rows]}


def is_guardian_of(cur, guardian_id, patient_id):
    cur.execute(
        "SELECT id FROM guardianships WHERE guardian_id = ? AND patient_id = ?",
        (guardian_id, patient_id)
    )
    return cur.fetchone() is not None


@app.get("/guardian/records")
def get_patient_records(patient_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    if not is_guardian_of(cur, current_user["id"], patient_id):
        conn.close()
        raise HTTPException(status_code=403, detail="이 대상자의 기록을 볼 권한이 없습니다")

    cur.execute("""
        SELECT records.*, users.name AS user_name
        FROM records
        JOIN users ON records.user_id = users.id
        WHERE records.user_id = ?
        ORDER BY records.date DESC
    """, (patient_id,))
    rows = cur.fetchall()

    result = []
    for row in rows:
        record = dict(row)
        record["warnings"] = get_warnings(cur, row["id"])
        result.append(record)

    conn.close()
    return {"count": len(result), "records": result}


class SignupIn(BaseModel):
    name: str
    password: str = Field(..., min_length=4)
    birth_year: int = 0
    gender: str = ""


@app.post("/signup")
def signup(user: SignupIn):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (name, password_hash, role, birth_year, gender) VALUES (?, ?, 'user', ?, ?)",
            (user.name, hash_password(user.password), user.birth_year, user.gender)
        )
        conn.commit()
        new_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="이미 존재하는 사용자입니다")
    conn.close()
    return {"id": new_id, "name": user.name}


@app.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE name = ?", (form.username,))
    row = cur.fetchone()
    conn.close()

    if row is None or not verify_password(form.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="이름 또는 비밀번호가 올바르지 않습니다")

    token = create_token(row["id"], row["name"], row["role"])
    return {"access_token": token, "token_type": "bearer"}


@app.get("/me")
def read_me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.get("/my/records")
def get_my_records(current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT records.*, users.name AS user_name
        FROM records
        JOIN users ON records.user_id = users.id
        WHERE records.user_id = ?
        ORDER BY records.date DESC
    """, (current_user["id"],))
    rows = cur.fetchall()

    result = []
    for row in rows:
        record = dict(row)
        record["warnings"] = get_warnings(cur, row["id"])
        result.append(record)

    conn.close()
    return {"count": len(result), "records": result}


@app.post("/my/records")
def create_my_record(record: RecordIn, current_user: dict = Depends(get_current_user)):
    record.user_id = current_user["id"]
    return create_record(record)


@app.get("/admin/records")
def get_all_records(admin: dict = Depends(require_admin)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT records.*, users.name AS user_name
        FROM records
        JOIN users ON records.user_id = users.id
        ORDER BY records.date DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return {"count": len(rows), "records": [dict(r) for r in rows]}


@app.get("/admin/users")
def get_all_users(admin: dict = Depends(require_admin)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, role, birth_year, gender, created_at FROM users")
    rows = cur.fetchall()
    conn.close()
    return {"count": len(rows), "users": [dict(r) for r in rows]}