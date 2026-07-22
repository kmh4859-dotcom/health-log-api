from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import os
from fastapi.responses import FileResponse
from datetime import datetime, timedelta


app = FastAPI(title="마이 헬스 로그 API", version="1.0")

DATA_FILE = "data.json"
records = []
next_id = 1


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json. dump({"records": records, "next_id": next_id}, f, ensure_ascii=False, indent=2)


def load_data():
    global records, next_id
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            records = data["records"]
            next_id = data["next_id"]


class RecordIn(BaseModel):
    date: str
    weight: float
    height: float
    systolic: int
    diastolic: int
    blood_sugar: int
    steps: int = 0
    sleep_hours: float = 0.0
    memo: str = ""


load_data()


def calculate_bmi(weight, height):
     height_m = height / 100
     bmi = weight / (height_m * height_m)
     return round(bmi, 1)


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
     

def make_warnings(bmi_category, bp_category, sugar_category):
     warnings = []
     if bmi_category == "비만":
          warnings.append("비만 상태입니다. 체중 관리가 필요합니다.")
     if bp_category == "고혈압":
          warnings.append("고혈압입니다. 혈압 관리가 필요합니다.")
     if sugar_category == "당뇨 의심":
          warnings.append("당뇨가 의심됩니다.검사를 권장합니다.")
     return warnings
          

@app.get("/")
def read_root():
    return FileResponse("index.html")

@app.post("/records")
def create_record(record: RecordIn):
    global next_id
    new_record = record.model_dump()
    new_record["id"] = next_id
    bmi = calculate_bmi(new_record["weight"], new_record["height"])
    new_record["bmi"] = bmi
    new_record["bmi_category"] = classify_bmi(bmi)
    new_record["bp_category"] = classify_bp(new_record["systolic"], new_record["diastolic"])
    new_record["sugar_category"] = classify_sugar(new_record["blood_sugar"])
    new_record["steps_category"] = classify_steps(new_record["steps"])
    new_record["sleep_category"] = classify_sleep(new_record["sleep_hours"])
    new_record["warnings"] = make_warnings(
         new_record["bmi_category"],
         new_record["bp_category"],
         new_record["sugar_category"]     
    ) 
    next_id += 1
    records.append(new_record)
    save_data()    
    return new_record

@app.get("/records")
def get_records():
	return {
		"count" : len(records),
		"records" : records
	}


@app.get("/records/{record_id}")
def get_record(record_id: int):
     for record in records:
          if record["id"] == record_id:
               return record
          raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")
     

@app.delete("/records/{record_id}")
def delete_record(record_id: int):
     for record in records:
          if record["id"] == record_id:
               records.remove(record)
               save_data()
               return {"message": "삭제되었습니다"}
     raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다")


@app.put("/records/{record_id}")
def update_record(record_id: int, record:RecordIn):
     for i in range(len(records)):
         if records[i]["id"] == record_id:
              updated = record.model_dump()
              updated["id"] = record_id
              bmi = calculate_bmi(updated["weight"], updated["height"])
              updated["bmi"] = bmi
              updated["bmi_category"] = classify_bmi(bmi)
              updated["bp_category"] = classify_bp(updated["systolic"], updated["diastolic"])
              updated["sugar_category"] = classify_sugar(updated["blood_sugar"])
              updated["steps_category"] = classify_steps(updated["steps"])
              updated["sleep_category"] = classify_sleep(updated["sleep_hours"])
              updated["warnings"] = make_warnings(
                   updated["bmi_category"],
                   updated["bp_category"],
                   updated["sugar_category"]
              )
              records[i] = updated
              save_data()
              return updated
     raise HTTPException(status_code=404, detail="기록을  찾을 수 없습니다")


@app.get("/search")
def search_records(start: str, end: str):
    result = []
    for record in records:
         if start <= record["date"] <= end:
              result.append(record)
    return {
         "count": len(result),
         "records": result
    }          


@app.get("/stats")
def get_stats():
    if len(records) == 0:
        return {"message": "기록이 없습니다"}
                       
    total_weight = 0
    total_bmi = 0
    for record in records:
        total_weight += record["weight"]
        total_bmi += record["bmi"]

    count = len(records)
    return {
         "count": count,
         "avg_weight": round(total_weight / count, 1),
         "avg_bmi": round(total_bmi / count, 1)
    }


@app.get("/weekly-report")
def weekly_report():
    today = datetime.now()
    week1_start = today - timedelta(days=7)
    week2_start = today - timedelta(days=14)

    def avg_weight(start, end):
        selected = []
        for r in records:
            record_date = datetime.strptime(r["date"], "%Y-%m-%d")
            if start <= record_date <end:
                selected.append(r["weight"])
        if len(selected) == 0:
             return None
        return round(sum(selected) / len(selected), 1)
    
    this_week = avg_weight(week1_start, today)
    last_week = avg_weight(week2_start, week1_start)

    change = None
    if this_week is not None and last_week is not None:
         change = round(this_week - last_week, 1)

    return {
         "this_week_avg_weight": this_week,
         "last_week_avg_weight": last_week,
         "change": change
    }