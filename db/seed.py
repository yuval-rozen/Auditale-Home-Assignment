# db/seed.py
"""
Populate the development DB with *realistic & correlated* SaaS usage so health scores
spread across healthy / at-risk / churn-risk segments.

Key changes:
- Segment-aware personas (enterprise / SMB / startup × healthy / at-risk / churn-risk)
- Correlated factors (adoption ↔ logins ↔ API; enterprise yields more tickets, etc.)
- Explicit API trend (prev30d vs curr30d means)
- 4 invoice cycles (3+ months), realistic on-time ratios per persona
"""

import argparse
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

# --- Add backend/ to sys.path so we can import your models & DB session ---
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.db import Base, engine, SessionLocal
from backend.models import Customer, Event, Invoice, SupportTicket, FeatureUsage

try:
    from faker import Faker
except ImportError:
    raise SystemExit("Install Faker: pip install faker")

fake = Faker()

SEGMENTS = ["enterprise", "SMB", "startup"]
FEATURES = ["Billing", "Analytics", "Automation", "Integrations", "Collaboration"]
INVOICE_MONTHS = 4  # 3+ months as requested

# ----------------------------
# Persona model (domain-driven)
# ----------------------------
@dataclass(frozen=True)
class Persona:
    # Baselines per 30 days (means), not hard caps
    logins_per_30_mu: Tuple[int, int]     # sample a mean in range; then daily noise
    api_prev30_mu:    Tuple[int, int]     # mean API calls in previous 30d
    api_trend_ratio:  Tuple[float, float] # multiply prev30 mean to get curr30 mean
    features_used_90: Tuple[int, int]     # distinct features used in last 90d
    tickets_90:       Tuple[int, int]     # support tickets opened in last 90d
    ontime_prob:      Tuple[float, float] # per-invoice on-time probability

# Segment × health personas
PERSONAS = {
    "enterprise": {
        "healthy":    Persona((16, 28), (300, 600), (1.05, 1.35), (3, 5), (1, 4),  (0.88, 0.96)),
        "at_risk":    Persona((8, 14),  (120, 260), (0.9, 1.1),   (2, 3), (3, 7),  (0.75, 0.9)),
        "churn_risk": Persona((0, 6),   (0, 80),    (0.6, 0.95),  (0, 1), (5, 10), (0.50, 0.75)),
    },
    "SMB": {
        "healthy":    Persona((12, 20), (180, 360), (1.0, 1.3),   (3, 5), (0, 3),  (0.9, 0.97)),
        "at_risk":    Persona((6, 12),  (60, 180),  (0.9, 1.1),   (1, 3), (2, 6),  (0.8, 0.92)),
        "churn_risk": Persona((0, 6),   (0, 80),    (0.6, 0.95),  (0, 1), (3, 9),  (0.55, 0.8)),
    },
    "startup": {
        "healthy":    Persona((8, 16),  (200, 420), (1.1, 1.5),   (2, 4), (0, 2),  (0.82, 0.95)),
        "at_risk":    Persona((4, 10),  (80, 200),  (0.85, 1.15), (1, 2), (1, 4),  (0.7, 0.9)),
        "churn_risk": Persona((0, 4),   (0, 60),    (0.5, 0.95),  (0, 1), (2, 6),  (0.4, 0.75)),
    },
}

# Prior over personas within each segment (tunable)
PERSONA_WEIGHTS = {
    "enterprise": [0.55, 0.30, 0.15],  # healthy, at_risk, churn_risk
    "SMB":        [0.50, 0.35, 0.15],
    "startup":    [0.45, 0.35, 0.20],
}

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed Postgres with realistic CORRELATED data.")
    p.add_argument("--customers", type=int, default=60)
    p.add_argument("--reset", action="store_true")
    p.add_argument("--seed", type=int, default=None)
    return p.parse_args()

def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def ensure_tables() -> None:
    Base.metadata.create_all(bind=engine)

def daterange_days(days_back: int) -> List[datetime]:
    now = datetime.utcnow()
    return [now - timedelta(days=i) for i in range(days_back, -1, -1)]

def rnd_dt_in_day(day: datetime) -> datetime:
    return day.replace(
        hour=random.randint(7, 21), minute=random.randint(0, 59), second=random.randint(0, 59)
    )

def new_customer() -> Customer:
    seg = random.choices(SEGMENTS, weights=[0.35, 0.45, 0.20], k=1)[0]
    return Customer(
        name=fake.company(),
        segment=seg,
        health_score=0.0,
        created_at=fake.date_time_between(start_date="-1y", end_date="now"),
    )

def choose_persona(segment: str) -> Tuple[str, Persona]:
    label = random.choices(["healthy", "at_risk", "churn_risk"], weights=PERSONA_WEIGHTS[segment], k=1)[0]
    return label, PERSONAS[segment][label]

def seed_customers(session, count: int) -> list:
    customers = [new_customer() for _ in range(count)]
    session.add_all(customers)
    session.commit()
    return customers

def _sample_int(lo_hi: Tuple[int, int]) -> int:
    lo, hi = lo_hi
    return random.randint(lo, hi)

def _sample_float(lo_hi: Tuple[float, float]) -> float:
    lo, hi = lo_hi
    return random.uniform(lo, hi)

def seed_logins_and_api_calls(session, customer_id: int, persona: Persona) -> None:
    """
    Build ~90 days of events.
    - Logins: daily Poisson-like counts around a per-30d mean.
    - API: explicit prev30d mean, curr30d mean = prev * trend_ratio.
    """
    days = daterange_days(90)
    events: List[Event] = []

    # --- login intensity over 90d ---
    logins_mu_30 = _sample_int(persona.logins_per_30_mu)
    login_mu_per_day = max(0.0, logins_mu_30 / 30.0)

    for day in days:
        # 60% of days see logins; draw small counts around mean
        if random.random() < 0.6 and login_mu_per_day > 0:
            count = max(0, int(random.gauss(mu=login_mu_per_day, sigma=0.8)))
            for _ in range(count):
                events.append(Event(
                    customer_id=customer_id, type="login", timestamp=rnd_dt_in_day(day), meta=None
                ))

    # --- API trend: previous 30 vs current 30 ---
    api_prev30_mu = _sample_int(persona.api_prev30_mu)
    ratio = _sample_float(persona.api_trend_ratio)
    api_curr30_mu = int(api_prev30_mu * ratio)
    api_mid30_mu  = int((api_prev30_mu + api_curr30_mu) / 2)

    # Slice days into [0..29]=prev, [30..59]=mid, [60..89]=curr (from oldest to newest)
    prev_slice = days[:30]
    mid_slice  = days[30:60]
    curr_slice = days[60:]

    def _emit_api(slice_days: List[datetime], mu_per_30: int):
        mu_daily = max(0.0, mu_per_30 / 30.0)
        for day in slice_days:
            # 90% of days have API activity
            if random.random() < 0.9 and mu_daily > 0:
                count = max(0, int(random.gauss(mu=mu_daily, sigma=5)))
                for _ in range(count):
                    events.append(Event(
                        customer_id=customer_id,
                        type="api_call",
                        timestamp=rnd_dt_in_day(day),
                        meta={"endpoint": random.choice(["/v1/items", "/v1/search", "/v1/ingest", "/v1/analytics"])}
                    ))
    _emit_api(prev_slice, api_prev30_mu)
    _emit_api(mid_slice,  api_mid30_mu)
    _emit_api(curr_slice, api_curr30_mu)

    if events:
        session.bulk_save_objects(events)
        session.commit()

def seed_feature_usage(session, customer_id: int, persona: Persona) -> None:
    distinct = _sample_int(persona.features_used_90)
    if distinct <= 0:
        return
    used = random.sample(FEATURES, k=min(distinct, len(FEATURES)))
    rows = []
    for fname in used:
        for _ in range(random.randint(2, 8)):
            day = datetime.utcnow() - timedelta(days=random.randint(0, 90))
            rows.append(FeatureUsage(customer_id=customer_id, feature_name=fname, used_at=rnd_dt_in_day(day)))
    if rows:
        session.bulk_save_objects(rows)
        session.commit()

def seed_support_tickets(session, customer_id: int, persona: Persona) -> None:
    count = _sample_int(persona.tickets_90)
    rows: List[SupportTicket] = []
    for _ in range(count):
        created = datetime.utcnow() - timedelta(days=random.randint(0, 90))
        status = random.choices(["open", "closed"], weights=[0.3, 0.7], k=1)[0]
        rows.append(SupportTicket(customer_id=customer_id, status=status, created_at=rnd_dt_in_day(created)))
    if rows:
        session.bulk_save_objects(rows)
        session.commit()

def seed_invoices(session, customer_id: int, persona: Persona) -> None:
    """
    4 recent invoices; each has on-time probability based on persona (late if paid > due).
    """
    now = datetime.utcnow()
    rows: List[Invoice] = []
    ontime_p = _sample_float(persona.ontime_prob)
    for m in range(INVOICE_MONTHS):
        due = datetime(now.year, now.month, 1) - timedelta(days=30 * m)
        amount = round(random.uniform(200, 3000), 2)
        if random.random() < 0.9:  # 10% months without invoice (trials / seasonal gaps)
            if random.random() < ontime_p:
                paid = due - timedelta(days=random.randint(0, 2))
            else:
                paid = due + timedelta(days=random.randint(1, 25))
            rows.append(Invoice(customer_id=customer_id, due_date=due, paid_date=paid, amount=amount))
    if rows:
        session.bulk_save_objects(rows)
        session.commit()

def main() -> None:
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed); Faker.seed(args.seed)

    if args.reset:
        print("⚠️  Dropping & recreating tables ..."); reset_db()
    else:
        ensure_tables()

    session = SessionLocal()

    existing = session.query(Customer).count()
    if existing > 0 and not args.reset:
        print(f"DB already has {existing} customers; use --reset to reseed.")
        session.close(); return

    target = max(50, int(args.customers))  # 50+ customers
    print(f"Creating {target} customers with segment-aware personas...")
    customers = seed_customers(session, target)

    print("Generating 90d activity + 4 invoices per customer...")
    for c in customers:
        label, persona = choose_persona(c.segment)
        seed_logins_and_api_calls(session, c.id, persona)
        seed_feature_usage(session, c.id, persona)
        seed_support_tickets(session, c.id, persona)
        seed_invoices(session, c.id, persona)

    # Summary
    ev   = session.query(Event).count()
    inv  = session.query(Invoice).count()
    tic  = session.query(SupportTicket).count()
    feat = session.query(FeatureUsage).count()
    print("\n✅ Seed complete")
    print(f"Customers:       {target}")
    print(f"Events:          {ev} (login/api_call)")
    print(f"Invoices:        {inv}")
    print(f"Support tickets: {tic}")
    print(f"Feature usage:   {feat}")
    session.close()

if __name__ == "__main__":
    main()
