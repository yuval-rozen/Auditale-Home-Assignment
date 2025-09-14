# PROJECT_SUMMARY.md

A consolidated technical summary of the Customer Health project across the three work sessions. Organized by the key deliverables:
(A) Docker/Compose setup, (B) Data seeding & health scoring, (C) Tests & coverage, (D) Deployment, (E) Dashboard (frontend & visualization).

---

## Project at a Glance

- **Stack**: FastAPI (Python) backend, PostgreSQL database, minimal HTML/JS dashboard (upgrade path to React + Material UI), containerized with Docker.
- **Key API Endpoints**: 
  - `GET /api/customers` – list customers
  - `GET /api/customers/{id}/health` – computed factor breakdown and final health score
  - `POST /api/customers/{id}/events` – ingest usage/billing/support events
  - `GET /api/dashboard` – serves dashboard UI (dev) or redirects to frontend (dockerized)
- **Health Score Factors (normalized 0–100)**: Login frequency (30d), Feature adoption (90d), Support ticket volume (90d), Invoice timeliness (recent invoices), API usage trend (30d vs previous 30d).
- **Target**: One-command run via `docker compose up --build`, plus deployable to a cloud host with a managed Postgres.

---

## (A) Docker/Compose Setup

### Services
- **db**: `postgres:14` with healthcheck (`pg_isready`), named volume for persistence.
- **backend**: Python 3.11 image running Uvicorn; waits for DB to become healthy; optional on-start seeding.
- **frontend**: NGINX serving `frontend/` (and proxying `/api` to backend when desired).

### Compose (Essentials)
- Remove deprecated `version:` key.
- Provide Postgres env vars under `db` and mirror them into `backend` (or construct `DATABASE_URL` in the backend entrypoint).
- Add healthcheck for `db` and `depends_on:` with `condition: service_healthy` for the backend.
- Map ports: `8000:8000` (backend), `8080:80` (frontend).

**Example compose essentials** (abridged):
```yaml
services:
  db:
    image: postgres:14
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d app"]
      interval: 5s
      timeout: 3s
      retries: 20
    volumes: [ "db_data:/var/lib/postgresql/data" ]

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    environment:
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
      POSTGRES_DB: app
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      # Optional seeding controls:
      SEED_ON_START: "true"    # run db/seed.py on container start
      SEED_CUSTOMERS: "80"     # number of customers to create
      SEED_RESET: "true"       # drop/recreate tables
    depends_on:
      db: { condition: service_healthy }
    ports: [ "8000:8000" ]

  frontend:
    build:
      context: frontend
      dockerfile: Dockerfile
    depends_on: [ backend ]
    ports: [ "8080:80" ]

volumes:
  db_data: {}
```

### Backend Image Entrypoint (Pattern)
- Wait for DB TCP socket to open.
- Optionally run `db/seed.py` (guarded by env flags).
- Start `uvicorn backend.main:app --host 0.0.0.0 --port 8000`.
- Add a container **HEALTHCHECK** against `/openapi.json`.

---

## (B) Data Seeding & Health Scoring

### Seed Dataset
- Seed **50–100 customers** across segments with realistic activity **over ~90 days**: logins, API calls, feature usage, support tickets, and invoices (some on-time, some late).
- Empirically validated row counts (e.g., events table tens of thousands of rows), indicating robust data volume to drive scoring.

### Factors & Windows (0–100 scale)
- **Login Frequency (30d)**: Normalize against a target (e.g., 20 logins → 100). Cap at 100.
- **Feature Adoption (90d)**: Distinct key features used / TOTAL_KEY_FEATURES × 100. Cap at 100.
- **Support Ticket Volume (90d)**: Fewer → better; monotonic penalty.
- **Invoice Timeliness (recent invoices)**: On-time / total. **Neutral (50)** when no billing history to avoid penalizing new customers.
- **API Usage Trend (30d vs previous 30d)**: Momentum; 50 = flat, >50 uptrend, <50 downtrend. Smooth extremes (0/0 → 50).

### Weights (example)
- Login 25%, Feature 25%, Support 20%, Invoice 20%, API Trend 10%.  
Final score = weighted average of factor scores.

### Worked Example
If factors: login=50, feature=60, support=60, invoice≈66.7, api=40  
Weighted sum = 12.5 + 15 + 12 + 13.334 + 4 = **56.83**.

---

## (C) Tests & Coverage

### Scope
- **Unit tests** for health utilities (pure functions): bounds [0..100], caps, neutral cases, monotonic behavior.
- **Integration tests** for endpoints with a test DB: 
  - `GET /api/customers` returns list.
  - `GET /api/customers/{id}/health` returns all factor keys and normalized score.
  - `POST /api/customers/{id}/events` mutates underlying data (e.g., extra login) and affects subsequent health calculation.
  - Robust error handling: `404` unknown customer; `422` validation errors for malformed payloads.

### Coverage Policy
- `pytest.ini` with `--cov=backend --cov-report=term-missing --cov-fail-under=80` for a single-command run.
- Expectation: ≥80% coverage overall, often ~90%+ given import-time execution of schemas/models. Optionally narrow/omit boilerplate files via `.coveragerc`.

### One-Command Run
```
docker compose run --rm backend pytest
# or locally (venv):
pytest -q
```

---

## (D) Deployment

### Cloud Target
- **Render** / **Railway** recommended for visibility and speed.
- Backend deployed as a Docker service; use managed Postgres; set env `DATABASE_URL` from provider.
- Frontend as static site (NGINX or host’s static site).
- If serving dashboard from backend in dev, enable CORS appropriately when serving frontend from another host in prod.

### Deployment Docs
- `DEPLOYMENT.md`: step-by-step, env vars, and public URL.
- Acceptance: public URL loads dashboard and can reach API endpoints.

---

## (E) Dashboard — Frontend & Visualization

### Minimal Dashboard (No-build path)
- Single `frontend/index.html` (HTML/JS/CSS) that fetches `/api/customers`, displays table, and on row click fetches `/api/customers/{id}/health` to render factor bars and score chip.
- Serve in dev via `GET /api/dashboard` (FastAPI `FileResponse` or redirect).

### Dockerized UX
- Frontend container (NGINX) serves the UI at `http://localhost:8080/`.
- Backend `GET /api/dashboard` may **redirect** to the frontend when `frontend/` is not present in the backend image (prevents StaticFiles errors in Docker).
- Optional upgrade path: swap to React + Material UI + Recharts with identical API calls.

---

## Acceptance Checklist

- **Run**: `docker compose up --build` brings up db + backend + frontend.
- **Data**: seed script creates realistic activity across multiple tables.
- **API**: three endpoints implemented and documented (Swagger/Redoc).
- **Dashboard**: loads real data; factors and score computed in detail view.
- **Tests**: unit + integration; coverage ≥ 80% in one command.
- **Deploy**: cloud URL is shareable; README & DEPLOYMENT guide included.

---

## Appendix — Key Files and Patterns

- `backend/main.py`: API routes and dashboard serving/redirect logic (dev vs Docker).
- `db/seed.py`: realistic customers, events, invoices, tickets, features.
- `backend/services/health.py`: factor scorers + weights + aggregator.
- `docker-compose.yml`: db (healthcheck), backend (depends_on, env), frontend (NGINX).
- `pytest.ini` / `.coveragerc`: coverage thresholds and optional omits.