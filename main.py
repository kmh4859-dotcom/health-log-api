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


@app.get("/")
def read_root():
    return {"message": "마이 헬스 로그 API"}

@app.post("/records")
def create_record(record: RecordIn):
    global next_id
    new_record = record.model_dump()
    new_record["id"] = next_id
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