- Set up **FastAPI** backend with `main.py` (“Hello World” endpoint).
- Installed dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`.

---

## Database Layer
- Added `db.py` with SQLAlchemy `engine`, `SessionLocal`, and `Base`.
- Chose **PostgreSQL** as the production DB (Dockerized via `docker-compose.yml`).
- Professional visibility (default in SaaS/data-heavy apps).
- Rich feature set (JSON, window functions).
- For local dev and tests, used **SQLite** for simplicity and speed.
- Added `seed.py` script to generate sample data:
- 50+ customers
- 3+ months of activity (logins, invoices, support tickets, API calls)
- Realistic segments: Enterprise, SMB, Startup
- Health levels varied: Healthy, At-risk, Churn-risk

---

## Health Score Methodology
Factors chosen (with windows & rationale):
1. **Login frequency (30d)**
- Frequent logins → engagement.
- Normalized against a target (20 logins/30d = 100).
2. **Feature adoption (90d)**
- Breadth of product usage → stickiness.
- Normalized against `TOTAL_KEY_FEATURES = 5`.
3. **Support load (90d)**
- More tickets → higher friction → lower score.
- Inverse mapping (0 tickets = 100).
4. **Invoice timeliness (counts)**
- Reliability of payments → financial health.
- **Counts-based logic**:
    - 0/0 invoices = neutral (50) → don’t penalize new customers.
    - Some invoices, none on time = 0 (bad).
5. **API usage trend (this 30d vs previous 30d)**
- Growth vs decline signals momentum.
- -100% → 0, flat → 50, +100% → 100, clamped.

Weights (tunable, based on SaaS benchmarks):
- Login frequency: 25%
- Feature adoption: 25%
- Support load: 20%
- Invoice timeliness: 20%
- API trend: 10%

---

## API Endpoints
- `GET /api/customers` → list customers.
- `GET /api/customers/{id}/health` → compute health breakdown + final score.
- `POST /api/customers/{id}/events` → ingest new event (login, api_call, etc.).
- `GET /` → sanity check.

---

## Documentation
- Fully documented `main.py` with rationale for:
- Time windows
- Neutrality handling
- Weighted aggregation
- Added docstrings and inline explanations to `services/health.py`.

---

## Testing
- **Unit tests (test_health_unit.py):**
- Validate scoring boundaries, clamping, neutrality, monotonicity.
- Weighted average correctness.
- **Integration tests (test_api_integration.py):**
- `GET /api/customers` returns expected list.
- `GET /api/customers/{id}/health` returns all factors in range.
- `POST /api/customers/{id}/events` increases loginFrequency.
- `GET /api/customers/{id}/health` for unknown ID → 404.
- **Fixtures (conftest.py):**
- Temporary SQLite file-based DB for test isolation.
- Dependency override for `get_db`.

---

## Current Status
- Backend fully functional with scoring logic.
- DB seeded with realistic demo data.
- Tests pass locally (`pytest -q`).
- Repo pushed to GitHub with clear commit history.

---

## Next Steps
- Build simple **frontend dashboard** (React + Material UI).
- Dockerize backend + frontend for unified deployment.
- Deploy on **Render** (or Railway) for a shareable live demo.
- Add architecture overview diagram to `README.md`.

---
