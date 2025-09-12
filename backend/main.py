"""
main.py
FastAPI application entrypoint for the Customer Health assignment.

What this service does
----------------------
- Exposes read-only endpoints for:
    * Listing customers (id, name, segment, raw health_score placeholder)
    * Computing a customer's *derived* health breakdown and final score
- Exposes a simple write endpoint to ingest activity events (login, api_call, etc.)
- Connects to PostgreSQL via SQLAlchemy and uses models defined in `models.py`

Design decisions (high level)
-----------------------------
- Tables are created on startup if they don't exist (idempotent, safe for local dev).
- Health score is NOT stored in the DB; it's computed on demand from recent activity:
    * Login frequency      -> 30d window (recent engagement)
    * Feature adoption     -> 90d window (breadth over time)
    * Support ticket load  -> 90d window (quarterly stability)
    * Invoice timeliness   -> last few invoices; **neutral (50)** if no billing history
    * API usage trend      -> last 30d vs previous 30d (momentum)
- Invoice timeliness uses a *counts-based* scorer so we can distinguish:
    * 0/0 invoices (no history)        -> neutral (50), not penalized
    * 0/3 invoices (all late)          -> 0 (bad)
- Endpoints are intentionally simple and documented for reviewer visibility.
"""

from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import Customer, Event, Invoice, SupportTicket, FeatureUsage
from .schemas import CustomerOut, HealthOut, EventIn
from .services.health import (
    WEIGHTS,
    score_login_frequency,
    score_feature_adoption,
    score_support_load,
    score_invoice_timeliness_counts,
    score_api_trend,
    weighted_score,
    TOTAL_KEY_FEATURES,
)

# You can customize title/description to look more professional in Swagger/ReDoc
app = FastAPI(
    title="Customer Health API",
    description="Compute customer health from usage, support, billing, and API trends.",
    version="0.1.0",
)
# Mount the whole frontend folder (so assets work if you add any later)
app.mount("/static", StaticFiles(directory="frontend"), name="static")
HOME = Path("frontend/home.html").resolve()
DASH = Path("frontend/dashboard.html").resolve()

@app.on_event("startup")
def startup_event() -> None:
    """
    App lifecycle hook: run once when the server starts.

    We create tables if they do not exist yet. This is idempotent (safe to call
    repeatedly). Seeding is *not* performed here—sample data is generated once
    via the separate `db/seed.py` script so the dataset remains stable.
    """
    Base.metadata.create_all(bind=engine)

@app.get("/app")          # homepage
def home_page(): return FileResponse(HOME)

@app.get("/api/dashboard")# dashboard
def dashboard_page(): return FileResponse(DASH)

@app.get("/api/customers", response_model=List[CustomerOut], tags=["Customers"])
def list_customers(db: Session = Depends(get_db)) -> List[CustomerOut]:
    """
    List customers (lightweight overview).

    Returns the raw database fields for customers. Note that `health_score` in the
    table is a placeholder; the *real* health is a derived value computed by
    `/api/customers/{id}/health` from recent activity.
    """
    return db.query(Customer).all()


@app.get("/api/customers/{customer_id}/health", response_model=HealthOut, tags=["Health"])
def customer_health(customer_id: int, db: Session = Depends(get_db)) -> HealthOut:
    """
    Compute a customer's health breakdown and final score.

    The score is a weighted average (0..100) of 5 normalized factors:
    - loginFrequency (30d)
    - featureAdoption (distinct features in 90d over TOTAL_KEY_FEATURES)
    - supportLoad (tickets in 90d; fewer -> better)
    - invoiceTimeliness (on-time % over recent invoices; **neutral if none**)
    - apiTrend (this 30d vs previous 30d; 50 = no change)

    Returns:
        HealthOut: { id, name, factors{...}, weights{...}, healthScore }
    """
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Define sliding windows used across factors
    now = datetime.utcnow()
    d30 = now - timedelta(days=30)
    d60 = now - timedelta(days=60)
    d90 = now - timedelta(days=90)

    # --- Login frequency (last 30d) ---
    # Frequent logins indicate engagement. We normalize against a target in services.health.
    logins_30d = db.execute(
        select(func.count()).select_from(Event)
        .where(Event.customer_id == customer_id)
        .where(Event.type == "login")
        .where(Event.timestamp >= d30)
    ).scalar() or 0
    login_s = score_login_frequency(logins_30d)

    # --- Feature adoption (distinct features used last 90d) ---
    # Breadth over time: the more "key features" a customer uses, the stickier they are.
    distinct_features = db.execute(
        select(func.count(func.distinct(FeatureUsage.feature_name)))
        .where(FeatureUsage.customer_id == customer_id)
        .where(FeatureUsage.used_at >= d90)
    ).scalar() or 0
    feature_s = score_feature_adoption(distinct_features, TOTAL_KEY_FEATURES)

    # --- Support load (tickets opened last 90d) ---
    # Fewer tickets imply less friction; 90d window smooths spikes.
    tickets_90d = db.execute(
        select(func.count()).select_from(SupportTicket)
        .where(SupportTicket.customer_id == customer_id)
        .where(SupportTicket.created_at >= d90)
    ).scalar() or 0
    support_s = score_support_load(tickets_90d)

    # --- Invoice timeliness (counts, not ratio) ---
    # Distinguish "no history" from "bad history" using counts:
    #   * total=0    -> neutral (50) to avoid penalizing new customers
    #   * on_time/total in (0..1] -> map to 0..100
    on_time = db.execute(
        select(func.count()).select_from(Invoice).where(
            (Invoice.customer_id == customer_id)
            & (Invoice.paid_date.isnot(None))
            & (Invoice.paid_date <= Invoice.due_date)
        )
    ).scalar() or 0
    total_invoices = db.execute(
        select(func.count()).select_from(Invoice)
        .where(Invoice.customer_id == customer_id)
    ).scalar() or 0
    invoice_s = score_invoice_timeliness_counts(
        on_time_invoices=on_time,
        total_invoices=total_invoices,
        neutral_if_no_history=True,  # <— key behavior documented in README
    )

    # --- API usage trend (30d vs previous 30d) ---
    # Momentum matters: downtrends (<50) can be early churn signals.
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

    # Aggregate factors and compute final weighted score
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


@app.post("/api/customers/{customer_id}/events", status_code=201, tags=["Ingest"])
def add_event(customer_id: int, payload: EventIn, db: Session = Depends(get_db)) -> dict:
    """
    Ingest an event for a customer (minimal audit/log pipeline).

    Accepted event types (from the assignment):
      - "login"
      - "api_call"
      - "feature_used"      (include {"feature_name": "..."} in meta)
      - "ticket_opened"
      - "invoice_paid"      (include {"amount": 123.45} in meta if desired)

    Notes:
      - This endpoint is intentionally permissive for demo purposes and assumes
        payload validation happens at the schema level (Pydantic).
      - These rows fuel the health computations:
          * login/api_call -> events table (engagement, API trend)
          * feature_used   -> feature_usage table (adoption breadth)
          * ticket_opened  -> support_tickets table (friction)
          * invoice_paid   -> invoices table (timeliness)
    """
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # If timestamp is omitted, treat as "now" to make manual testing easy.
    ts = datetime.fromisoformat(payload.timestamp) if payload.timestamp else datetime.utcnow()

    # Store the raw event as-is in the events table (simple unified log)
    ev = Event(customer_id=customer_id, type=payload.type, timestamp=ts, meta=payload.meta or {})
    db.add(ev)
    db.commit()
    db.refresh(ev)

    return {"id": ev.id, "status": "created"}

@app.get("/api/dashboard")
async def dashboard():
    return FileResponse(INDEX)

@app.get("/", tags=["Meta"])
def root() -> dict:
    """
    Lightweight service check and human-friendly note.
    """
    return {"message": "Hello from FastAPI"}

