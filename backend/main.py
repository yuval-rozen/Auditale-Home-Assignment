# main.py
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from db import Base, engine, get_db
from models import Customer
from schemas import CustomerOut

app = FastAPI()

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)

    # seed a few rows if empty
    with engine.begin() as conn:
        result = conn.execute(select(func.count()).select_from(Customer.__table__))
        count = result.scalar() or 0
        if count == 0:
            conn.execute(
                Customer.__table__.insert(),
                [
                    {"name": "Acme Co", "segment": "Enterprise", "health_score": 72.5},
                    {"name": "Beta Labs", "segment": "Startup", "health_score": 58.0},
                    {"name": "CornerShop", "segment": "SMB", "health_score": 43.0},
                ],
            )

@app.get("/api/customers", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).all()

@app.get("/")
def root():
    return {"message": "Hello from FastAPI"}
