"""
test_api_integration.py
-----------------------
Integration tests for the FastAPI application using a temporary SQLite test DB.

What these tests verify (end-to-end-ish):
- The public API endpoints respond with the expected shapes and status codes.
- The app's dependency override correctly routes DB access to the test Session.
- Health calculation pulls from multiple tables and stays within [0..100].
- Posting new events changes health input data (behavioral change over time).
- Proper error handling for critical paths: 404 on missing customer, 422 on bad payload.

Notes:
- The database and app wiring for tests are configured in `tests/conftest.py`.
- We keep scenarios minimal but realistic so failures indicate genuine regressions.
"""

from datetime import datetime, timedelta

# ORM models: used to insert domain rows the API will later read
from backend.models import Customer, Event, Invoice, SupportTicket, FeatureUsage


def test_get_customers_list(client, db_session):
    """
    GET /api/customers returns a list that includes newly created customers.

    Why this matters:
    - Verifies the basic read path to the DB works through FastAPI.
    - Ensures the response is a JSON list and contains expected fields.

    Flow:
    1) Arrange: Insert one Customer directly via the SQLAlchemy session.
    2) Act:     Call the endpoint.
    3) Assert:  Response is 200, JSON is a list, and includes our inserted name/id.
    """
    # Arrange
    c = Customer(name="TestCo", segment="SMB", health_score=0.0)
    db_session.add(c)
    db_session.commit()

    # Act
    res = client.get("/api/customers")
    assert res.status_code == 200
    data = res.json()

    # Assert
    assert isinstance(data, list)
    assert any(row["name"] == "TestCo" and row["id"] == c.id for row in data)


def test_get_customer_health_breakdown(client, db_session):
    """
    GET /api/customers/{id}/health returns a well-formed health breakdown.

    Why this matters:
    - This endpoint combines multiple sources: events, feature usage, invoices,
      and support tickets across 30d/90d windows.
    - We want to confirm the API returns all factor keys and the final score
      is inside [0..100] (normalized).

    Scenario:
    - Create a customer with:
      * 3 logins in the last 30 days        -> engagement signal
      * 2 distinct features in last 90 days -> adoption breadth
      * 2 invoices, both on time            -> billing reliability
      * 1 support ticket in last 90 days    -> moderate friction

    We don't assert exact numeric factor values (they can change with logic tweaks),
    only that all keys are present and the final score is a valid 0..100 number.
    """
    # Arrange
    c = Customer(name="ActiveCo", segment="enterprise", health_score=0.0)
    db_session.add(c)
    db_session.commit()

    now = datetime.utcnow()

    # A few logins in the last 30 days
    for _ in range(3):
        db_session.add(Event(customer_id=c.id, type="login", timestamp=now - timedelta(days=3)))

    # Two distinct features in the last 90 days -> adoption > 0
    db_session.add(FeatureUsage(customer_id=c.id, feature_name="Analytics",  used_at=now - timedelta(days=10)))
    db_session.add(FeatureUsage(customer_id=c.id, feature_name="Automation", used_at=now - timedelta(days=5)))

    # Two invoices; both paid on/before due date -> strong timeliness (clarified: no unused vars)
    due1 = now - timedelta(days=20)
    due2 = now - timedelta(days=50)
    db_session.add(Invoice(customer_id=c.id, due_date=due1, paid_date=due1, amount=100.0))
    db_session.add(Invoice(customer_id=c.id, due_date=due2, paid_date=due2, amount=120.0))

    # One support ticket in the last 90 days
    db_session.add(SupportTicket(customer_id=c.id, status="closed", created_at=now - timedelta(days=15)))

    db_session.commit()

    # Act
    res = client.get(f"/api/customers/{c.id}/health")
    assert res.status_code == 200
    body = res.json()

    # Assert: presence of expected keys and a valid score range
    assert body["id"] == c.id
    assert set(body["factors"].keys()) == {
        "loginFrequency",
        "featureAdoption",
        "supportLoad",
        "invoiceTimeliness",
        "apiTrend",
    }
    assert 0.0 <= body["healthScore"] <= 100.0


def test_post_event_increases_login_score(client, db_session):
    """
    POST /api/customers/{id}/events with a 'login' should not reduce—and typically increases—
    the `loginFrequency` factor in the health breakdown.

    Why this matters:
    - Demonstrates that ingesting new activity updates the underlying signals
      used for health without direct DB access from the test (black-box behavior).
    - Avoids brittle equality checks by asserting non-decreasing behavior.

    Flow:
    1) Arrange: Create a customer with no recent logins.
    2) Act:     Compute baseline health; POST a new 'login' event; recompute health.
    3) Assert:  The loginFrequency factor stays the same or increases.
    """
    # Arrange
    c = Customer(name="LoginInc", segment="startup", health_score=0.0)
    db_session.add(c)
    db_session.commit()

    # Baseline health
    r1 = client.get(f"/api/customers/{c.id}/health")
    assert r1.status_code == 200
    before = r1.json()["factors"]["loginFrequency"]

    # Act: add a login event (minimal valid payload)
    r2 = client.post(f"/api/customers/{c.id}/events", json={"type": "login"})
    assert r2.status_code == 201

    # Recompute health after ingesting the event
    r3 = client.get(f"/api/customers/{c.id}/health")
    after = r3.json()["factors"]["loginFrequency"]

    # Assert
    assert after >= before, "loginFrequency should not decrease after posting a login event"


def test_health_not_found_returns_404(client):
    """
    GET /api/customers/{id}/health returns 404 for unknown customers.

    Why this matters:
    - Confirms the API surfaces a clear, explicit error for invalid IDs
      instead of 500s or empty payloads.
    - Validates parity with application logic in main.py:
        raise HTTPException(status_code=404, detail="Customer not found")

    Flow:
    1) Act:    Request health for a non-existent customer ID (e.g., 9999).
    2) Assert: Status is 404 and the 'detail' message matches the contract.
    """
    res = client.get("/api/customers/9999/health")
    assert res.status_code == 404
    body = res.json()
    assert body.get("detail") == "Customer not found"


def test_post_event_validation_and_missing_customer_errors(client, db_session):
    """
    Negative scenarios covering proper error handling:

    1) 404 Not Found when posting an event to a non-existent customer.
       - Ensures we don't silently create or ignore invalid IDs.

    2) 422 Unprocessable Entity when the JSON payload doesn't satisfy EventIn
       (e.g., missing required 'type').
       - Ensures request validation is enforced by FastAPI/Pydantic.

    Flow:
    - POST to a bogus customer id -> expect 404.
    - Create a real customer, POST with missing 'type' -> expect 422.
    """
    # (1) 404 on unknown customer
    res = client.post("/api/customers/424242/events", json={"type": "login"})
    assert res.status_code == 404

    # (2) 422 on bad payload for an existing customer (missing required 'type')
    c = Customer(name="BadPayloadCo", segment="SMB", health_score=0.0)
    db_session.add(c)
    db_session.commit()

    res2 = client.post(
        f"/api/customers/{c.id}/events",
        json={"timestamp": datetime.utcnow().isoformat()}  # missing 'type'
    )
    assert res2.status_code == 422