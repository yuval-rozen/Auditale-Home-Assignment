"""
db/seed.py

Populate the development database with realistic sample data so that:
- Health-score factors have meaningful inputs
- The dashboard / API endpoints return interesting results
- Reviewers can evaluate behavior across "healthy", "at-risk", and "churn-risk" customers

This script connects to the SAME Postgres instance your app uses,
imports your SQLAlchemy models from backend/, and inserts randomized rows.

Run from project root (where docker-compose.yml is):
    python db/seed.py --customers 80 --reset

Flags:
  --customers N   Number of customers to create (default: 60)
  --reset         Drop all known tables and recreate them before seeding (dev only)
  --seed S        Random seed for reproducibility (default: none)
"""

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# --- Add backend/ to sys.path so we can import your models & DB session ---
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]   # project root
sys.path.insert(0, str(ROOT))                # make 'backend' importable as a package

from backend.db import Base, engine, SessionLocal
from backend.models import (
    Customer,
    Event,
    Invoice,
    SupportTicket,
    FeatureUsage,
)

# Third-party helpers
try:
    from faker import Faker
except ImportError:
    raise SystemExit(
        "Missing dependency: faker\n"
        "Install it in your backend venv: pip install faker\n"
        "Then re-run: python db/seed.py"
    )

# -----------------------------
# Configuration & factor intent
# -----------------------------
# Health-score factors (for reference):
# - Login frequency             -> derived from Event rows with type='login'
# - API usage trends            -> derived from Event rows with type='api_call' (compare last 30d vs prior 30d)
# - Feature adoption rate       -> derived from FeatureUsage (distinct features used in last 90d)
# - Support ticket volume       -> derived from SupportTicket (tickets opened last 90d)
# - Invoice payment timeliness  -> derived from Invoice (paid_date <= due_date ratio)

SEGMENTS = ["enterprise", "SMB", "startup"]
FEATURES = ["Billing", "Analytics", "Automation", "Integrations", "Collaboration"]

# You can tune these to bias how "active" seeded customers are.
P_LOGIN_BASE_PER_30D = (0, 30)     # logins per 30 days: random.randint(2, 30)
P_API_BASE_PER_30D   = (20, 500)   # api calls per 30 days
P_FEATURES_USED      = (0, 5)      # distinct features in last 90 days
P_TICKETS_PER_90D    = (0, 10)     # tickets opened last 90 days
INVOICE_MONTHS       = 3           # create 3 monthly invoices

fake = Faker()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Postgres with realistic data.")
    parser.add_argument("--customers", type=int, default=60, help="Number of customers to create (default: 60)")
    parser.add_argument("--reset", action="store_true", help="Drop & recreate tables (dev only)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (for reproducible runs)")
    return parser.parse_args()


def reset_db() -> None:
    """
    Danger: drops and recreates ALL tables known to SQLAlchemy's Base metadata.
    Use for DEV ONLY to start with a clean slate.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def ensure_tables() -> None:
    """
    Create tables if they don't exist yet.
    Safe to call repeatedly (no-ops if already created).
    """
    Base.metadata.create_all(bind=engine)


def daterange_days(days_back: int) -> List[datetime]:
    """
    Helper: returns a list of datetimes for each day from now - days_back .. now
    Used to scatter events across ~90 days.
    """
    now = datetime.utcnow()
    return [now - timedelta(days=offset) for offset in range(days_back, -1, -1)]


def rnd_dt_in_day(day: datetime) -> datetime:
    """
    Return a random time within the provided day (UTC).
    Make seeded data look more natural (events not all at midnight).
    """
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return datetime(day.year, day.month, day.day, hour, minute, second)


def new_customer() -> Customer:
    """
    Create (but do not persist) a Customer ORM object with randomized fields.
    """
    return Customer(
        name=fake.company(),
        segment=random.choices(SEGMENTS, weights=[0.35, 0.45, 0.20], k=1)[0],  # slightly more SMB/enterprise
        health_score=0.0,  # will be computed by your API later; we store 0 for now
        created_at=fake.date_time_between(start_date="-1y", end_date="now"),
    )


def seed_customers(session, count: int) -> list:
    customers = [new_customer() for _ in range(count)]
    session.add_all(customers)   # <-- use add_all, not bulk_save_objects
    session.commit()
    return customers


def seed_logins_and_api_calls(session, customer_id: int) -> None:
    """
    Create ~90 days worth of login and API-call events for a customer.
    Login frequency -> number of 'login' events in last 30 days
    API trend -> compare 'api_call' count in last 30 days vs previous 30
    """
    # How active is this customer? Add variance.
    logins_per_30 = random.randint(*P_LOGIN_BASE_PER_30D)
    api_per_30 = random.randint(*P_API_BASE_PER_30D)

    # Spread events across ~90 days, with some random daily counts.
    days = daterange_days(90)

    events: List[Event] = []

    for day in days:
        # Logins: only some days have logins
        if random.random() < 0.6:  # 60% of days have logins
            count_login_today = max(0, int(random.gauss(mu=logins_per_30 / 30.0, sigma=0.8)))
            for _ in range(count_login_today):
                events.append(Event(
                    customer_id=customer_id,
                    type="login",
                    timestamp=rnd_dt_in_day(day),
                    meta=None
                ))

        # API calls: most days have API calls
        if random.random() < 0.9:  # 90% of days have API calls
            count_api_today = max(0, int(random.gauss(mu=api_per_30 / 30.0, sigma=5)))
            for _ in range(count_api_today):
                events.append(Event(
                    customer_id=customer_id,
                    type="api_call",
                    timestamp=rnd_dt_in_day(day),
                    meta={"endpoint": random.choice(["/v1/items", "/v1/search", "/v1/ingest", "/v1/analytics"])}
                ))

    if events:
        session.bulk_save_objects(events)
        session.commit()


def seed_feature_usage(session, customer_id: int) -> None:
    """
    Record which features were used in last 90 days.
    Feature adoption -> count distinct features used vs total key features.
    """
    # Each customer adopts a random number of features.
    distinct_count = random.randint(*P_FEATURES_USED)
    used_features = random.sample(FEATURES, k=distinct_count) if distinct_count > 0 else []

    rows = []
    for fname in used_features:
        # use it a few times over the last 90 days
        for _ in range(random.randint(1, 6)):
            day = datetime.utcnow() - timedelta(days=random.randint(0, 90))
            rows.append(FeatureUsage(
                customer_id=customer_id,
                feature_name=fname,
                used_at=rnd_dt_in_day(day),
            ))

    if rows:
        session.bulk_save_objects(rows)
        session.commit()


def seed_support_tickets(session, customer_id: int) -> None:
    """
    Support ticket volume -> how many tickets opened in last 90 days.
    We create some open and some closed tickets.
    """
    tickets_to_create = random.randint(*P_TICKETS_PER_90D)
    rows: List[SupportTicket] = []
    for _ in range(tickets_to_create):
        created = datetime.utcnow() - timedelta(days=random.randint(0, 90))
        status = random.choices(["open", "closed"], weights=[0.3, 0.7], k=1)[0]
        rows.append(SupportTicket(
            customer_id=customer_id,
            status=status,
            created_at=rnd_dt_in_day(created),
        ))

    if rows:
        session.bulk_save_objects(rows)
        session.commit()


def seed_invoices(session, customer_id: int) -> None:
    """
    Seed invoice history for a customer (realistic but backend-aligned).

    Behavior:
      - Generate up to `INVOICE_MONTHS` past months (default: 3).
      - For each month, there's an 85% chance the customer actually has an invoice
        (some are new/free-trial → gaps are realistic).
      - ~10% of customers behave like "chronic late payers" for this run.
        * Chronic late payers are late ~80% of the time.
        * Others pay on time ~85% of the time.
      - Amounts vary between $200 and $3000.

    IMPORTANT ALIGNMENT:
      - "On-time" here means paid_date <= due_date (no grace),
        matching the backend health logic that counts on-time using:
          paid_date <= due_date
    """
    now = datetime.utcnow()
    rows: List[Invoice] = []

    # Decide once per customer if they behave like a chronic late payer
    late_payer = random.random() < 0.10  # ~10%

    for m in range(INVOICE_MONTHS):
        # Due on the 1st of each month going backwards (this month, last month, etc.)
        due = datetime(now.year, now.month, 1) - timedelta(days=30 * m)
        amount = round(random.uniform(200, 3000), 2)

        # 90% chance this month actually has an invoice
        if random.random() < 0.9:
            ontime_prob = 0.20 if late_payer else 0.9

            if random.random() < ontime_prob:
                # On-time: paid on/before due_date (allow a bit early)
                paid = due - timedelta(days=random.randint(0, 2))  # 0 = same day
            else:
                # Late: strictly AFTER due_date
                paid = due + timedelta(days=random.randint(1, 25))

            rows.append(Invoice(
                customer_id=customer_id,
                due_date=due,
                paid_date=paid,
                amount=amount,
            ))

    if rows:
        session.bulk_save_objects(rows)
        session.commit()


def main() -> None:
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        Faker.seed(args.seed)

    if args.reset:
        print("⚠️  Dropping & recreating tables (dev only)...")
        reset_db()
    else:
        ensure_tables()

    session = SessionLocal()

    # If DB already has customers, avoid duplicating unless reset was used.
    existing = session.query(Customer).count()
    if existing > 0 and not args.reset:
        print(f"Database already has {existing} customers. Nothing to do. "
              f"Use --reset to rebuild and reseed, or delete rows manually.")
        session.close()
        return

    # 1) Customers
    target = max(1, int(args.customers))
    print(f"Creating {target} customers...")
    customers = seed_customers(session, target)

    # 2) Activity per customer
    print("Creating activity for each customer (logins, api calls, features, tickets, invoices)...")
    for c in customers:
        seed_logins_and_api_calls(session, c.id)
        seed_feature_usage(session, c.id)
        seed_support_tickets(session, c.id)
        seed_invoices(session, c.id)

    # 3) Summary
    cust = session.query(Customer).count()
    ev   = session.query(Event).count()
    inv  = session.query(Invoice).count()
    tic  = session.query(SupportTicket).count()
    feat = session.query(FeatureUsage).count()

    print("\n✅ Seed complete")
    print(f"Customers:       {cust}")
    print(f"Events:          {ev}  (login/api_call)")
    print(f"Invoices:        {inv}")
    print(f"Support tickets: {tic}")
    print(f"Feature usage:   {feat}")

    session.close()


if __name__ == "__main__":
    main()
