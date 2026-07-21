from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="마이 헬스 로그 API", version="1.0")

records = []
next_id = 1

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
    return {"message": "마이 헬스 로그 API"}

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
    new_record["warnings"] = make_warnings(
         new_record["bmi_category"],
         new_record["bp_category"],
         new_record["sugar_category"]     
    ) 
    next_id += 1
    records.append(new_record)
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
              updated["warnings"] = make_warnings(
                   updated["bmi_category"],
                   updated["bp_category"],
                   updated["sugar_category"]
              )
              records[i] = updated
              return updated
     raise HTTPException(status_code=404, detail="기록을  찾을 수 없습니다")