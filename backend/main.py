# main.py
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from db import Base, engine, get_db
from models import Customer
from schemas import CustomerOut
# add imports
from datetime import datetime, timedelta
from sqlalchemy import select, func, case
from fastapi import HTTPException
from services.health import (
    WEIGHTS,
    score_login_frequency,
    score_feature_adoption,
    score_support_load,
    score_invoice_timeliness,
    score_api_trend,
    weighted_score,
    TOTAL_KEY_FEATURES,
)
from models import Customer, Event, Invoice, SupportTicket, FeatureUsage
from schemas import CustomerOut, HealthOut, EventIn


app = FastAPI()

@app.on_event("startup")
def startup_event():
    # Create tables if they are missing (safe, idempotent)
    Base.metadata.create_all(bind=engine)
    # No seeding here; data comes from one-time seed script


@app.get("/api/customers", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).all()

@app.get("/api/customers/{customer_id}/health", response_model=HealthOut)
def customer_health(customer_id: int, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    now = datetime.utcnow()
    d30 = now - timedelta(days=30)
    d60 = now - timedelta(days=60)
    d90 = now - timedelta(days=90)

    # --- login frequency (last 30d) ---
    logins_30d = db.execute(
        select(func.count()).select_from(Event)
        .where(Event.customer_id == customer_id)
        .where(Event.type == "login")
        .where(Event.timestamp >= d30)
    ).scalar() or 0
    login_s = score_login_frequency(logins_30d)

    # --- feature adoption (distinct features used last 90d) ---
    distinct_features = db.execute(
        select(func.count(func.distinct(FeatureUsage.feature_name)))
        .where(FeatureUsage.customer_id == customer_id)
        .where(FeatureUsage.used_at >= d90)
    ).scalar() or 0
    feature_s = score_feature_adoption(distinct_features, TOTAL_KEY_FEATURES)

    # --- support load (tickets opened last 90d) ---
    tickets_90d = db.execute(
        select(func.count()).select_from(SupportTicket)
        .where(SupportTicket.customer_id == customer_id)
        .where(SupportTicket.created_at >= d90)
    ).scalar() or 0
    support_s = score_support_load(tickets_90d)

    # --- invoice timeliness (ratio on-time across all invoices) ---
    on_time = db.execute(
        select(func.count()).select_from(Invoice).where(
            (Invoice.customer_id == customer_id) &
            (Invoice.paid_date.isnot(None)) &
            (Invoice.paid_date <= Invoice.due_date)
        )
    ).scalar() or 0
    total_invoices = db.execute(
        select(func.count()).select_from(Invoice).where(Invoice.customer_id == customer_id)
    ).scalar() or 0
    on_time_ratio = (on_time / total_invoices) if total_invoices else 0.0
    invoice_s = score_invoice_timeliness(on_time_ratio)

    # --- API trend (calls this 30d vs previous 30d) ---
    api_curr = db.execute(
        select(func.count()).select_from(Event)
        .where(Event.customer_id == customer_id)
        .where(Event.type == "api_call")
        .where(Event.timestamp >= d30)
    ).scalar() or 0
    api_prev = db.execute(
        select(func.count()).select_from(Event)
        .where(Event.customer_id == customer_id)
        .where(Event.type == "api_call")
        .where(Event.timestamp < d30)
        .where(Event.timestamp >= d60)
    ).scalar() or 0
    api_s = score_api_trend(api_curr, api_prev)

    factors = {
        "loginFrequency": login_s,
        "featureAdoption": feature_s,
        "supportLoad": support_s,
        "invoiceTimeliness": invoice_s,
        "apiTrend": api_s,
    }
    final_score = weighted_score(factors)

    return HealthOut(
        id=customer.id,
        name=customer.name,
        factors=factors,
        weights=WEIGHTS,
        healthScore=final_score,
    )

@app.post("/api/customers/{customer_id}/events", status_code=201)
def add_event(customer_id: int, payload: EventIn, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    ts = datetime.fromisoformat(payload.timestamp) if payload.timestamp else datetime.utcnow()
    ev = Event(customer_id=customer_id, type=payload.type, timestamp=ts, meta=payload.meta or {})
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return {"id": ev.id, "status": "created"}


@app.get("/")
def root():
    return {"message": "Hello from FastAPI"}

