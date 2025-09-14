# AI Collaboration Evidence
**Project:** Customer Health App  
**Sources reviewed:** `first_steps_of_project.txt`, `more_development_steps.txt`, `3rd_dev_step.txt`

This document consolidates how AI tools were used throughout development, why specific
design decisions were made, and concrete evidence of iteration on AI‑generated suggestions.  
It focuses on the complete lifecycle: requirements clarification → architecture → Docker/Compose →
data modeling & seeding → health‑score methodology → API & tests → dashboard (frontend & visualization) →
deployment & ops.

---


## 1) Documentation of AI Tool Usage

### 1.1 Requirements & Architecture
- **Clarified success criteria**: “one‑command up” via Docker Compose, seeded data, a working dashboard,
  and API docs available at `/docs`. The conversations explicitly prioritized a realistic demo: seed 50–100
  customers, 3 months of events, multiple segments, visible distribution of health states.
- **API surface** (guided and refined):
  - `GET /api/customers` — list with primary fields and (optionally) current `healthScore`.
  - `GET /api/customers/{id}/health` — factor breakdown (normalized 0–100) + weighted final score.
  - `POST /api/customers/{id}/events` — ingest usage/billing/support activity for iterative scoring.
  - **Dev dashboard** served via FastAPI for local runs, **redirected** to NGINX in Docker (see §3.2).
- **Documentation UX**: ReDoc preferred as default (clean single‑page), optional Swagger at `/swagger`.
  Rationale: evaluators can scan endpoints fast, without collapsing huge schemas.

### 1.2 Docker/Compose & Runtime
- **Compose guidance**:
  - Use **PostgreSQL 14** (later pinned explicitly after a version mismatch; see §3.1).
  - Add a **db healthcheck** using `pg_isready`, wire **backend depends_on: service_healthy`**.
  - Expose ports `8000:8000` (backend), and `8080:80` (frontend via NGINX).
  - Remove `version:` (deprecated in Compose v2).
- **Entrypoint pattern** (backend):
  1) Wait for DB (loop on TCP/`pg_isready`).  
  2) (Optional) run `db/seed.py` based on env flags (e.g., `SEED_ON_START=true`).  
  3) Start Uvicorn.  
  4) (Optional) container HEALTHCHECK hitting `/openapi.json`.
- **NGINX config** (frontend):
  - Serve static files; **proxy `/api/*` to backend** so the UI can call the API same‑origin.
  - Convenience routes (`/app`, `/api/dashboard`) map to `home.html` / `dashboard.html` for nice URLs.

### 1.3 Data Model & Seeding
- **Entities**: `customers`, `events` (login/API/feature/support), `invoices`, `features`.
- **Seed design**:
  - 50–100 customers across segments (Enterprise/SMB/Startup).  
  - ~90 days of activity with realistic distributions (some very active, some silent).  
  - Billings with on‑time and late invoices.  
  - Feature usage across a core set of “key features” for adoption scoring.
- **Validation**: recommended **row‑count checks** after seeding (e.g., thousands of events) to ensure healthy data
  volume for meaningful scores and charts.

### 1.4 Health‑Score Methodology
- **Factors (0–100, normalized)**:
  - **Login frequency (30d)** — capped at a target (e.g., 20 logins → 100).
  - **Feature adoption (90d)** — used_features / total_key_features × 100.
  - **Support ticket volume (90d)** — fewer is better; monotonic penalty.
  - **Invoice timeliness (recent invoices)** — on‑time / total. **Neutral (50)** if no billing history.
  - **API usage trend (30d vs previous 30d)** — momentum: 50 = flat; uptrend >50; downtrend <50; **0/0 → 50**.
- **Weights (example)**: Login 25%, Feature 25%, Support 20%, Invoice 20%, API Trend 10%.
- **Rationale**: mirrors common SaaS health definitions—engagement & adoption lead; support/billing
  reflect friction/renewal risk; API trend captures momentum.

### 1.5 API, Validation & Documentation
- **Schematics**: Pydantic models for list/detail; clear factor keys and final score.  
- **Validation**: consistent 404 for unknown customer; 422 for bad payloads; typed enums for event kinds.  
- **Docs**: ReDoc at `/`, Swagger at `/swagger`, OpenAPI JSON at `/openapi.json` for healthchecks.

### 1.6 Testing & Coverage
- **Unit tests** for factor scorers (pure functions): bounds [0..100], caps, monotonicity, neutral cases,
  smoothing (e.g., 0/0 → 50), rounding.
- **Integration tests** for API: list customers; compute health; mutate via events and observe score changes;
  negative cases (404/422).
- **Coverage policy**: `pytest -q --cov=backend --cov-report=term-missing --cov-fail-under=80`.
  Optionally use `.coveragerc` to omit boilerplate (e.g., `db/__init__.py`, migrations) while keeping
  core logic tested.

### 1.7 Dashboard (Frontend & Visualization)
- **No‑build HTML/JS** prototype (fast to verify): a table of customers; selecting a row fetches
  `/api/customers/{id}/health` and renders factor **bars** and a **score chip**.
- **In‑Docker serving strategy**: in dev, FastAPI can serve files; in Docker, **redirect** to the NGINX‑served UI
  to avoid missing `frontend/` inside the backend image.
- **Accessibility & UX**: keyboard focus for rows, visible labels for bars, clear colors for Good/Warning/Poor.

### 1.8 Deployment & Ops
- **Local acceptance**: `docker compose up --build` → dashboard reachable, API healthy, docs readable.
- **Cloud path**: Docker → **Render** or **Railway** with managed Postgres. Configure `DATABASE_URL`,
  CORS (if serving UI on a different host), and a public URL for reviewers.

---

## 2) Quality of Research & Implementation Decisions

1. **Database choice** — *PostgreSQL* over SQLite/MySQL for robustness, enterprise feel, and clear migration path.
2. **Compose health** — add `healthcheck` + `depends_on: service_healthy` to avoid race conditions
   (backend trying to connect before Postgres is ready).
3. **Entrypoint “wait‑for‑DB”** — avoids brittle sleeps; leverages `pg_isready` or TCP probing.
4. **Seeding realism** — ensures meaningful *variance* in health scores (healthy ↔ at‑risk), making the
   dashboard credible.
5. **Health factors & windows** — balances *engagement* (login/adoption) with *friction* (tickets, billing) and
   *momentum* (API trend). Neutral‑when‑missing billing avoids punishing new customers.
6. **Score normalization** — caps & smoothing guard against outliers (e.g., 0/0 → 50 rather than noise).
7. **JSON shape** — chose **camelCase** (e.g., `healthScore`) for frontend ergonomics, with Pydantic aliases to
   avoid refactors in Python.
8. **Docs UX** — ReDoc as the clean default; Swagger retained for interactive testing.
9. **Testing bar** — ≥80% coverage enforces meaningful tests while keeping iteration velocity high. Coverage
   *focuses* on business logic; boilerplate can be omitted via `.coveragerc` to prevent false confidence.
10. **Dockerized UI strategy** — serve static via NGINX (fast, cacheable); only **redirect** from FastAPI
    (`/api/dashboard`) when running in containers. Reduces coupling and avoids missing‑folder failures.
11. **Deployment** — Render/Railway recommended for fast reviewer access and trivial `DATABASE_URL` setup.

---

## 3) Evidence of Iterating on AI‑Generated Suggestions (with concrete examples)

### 3.1 Postgres version mismatch (persisted volume vs newer image)
- **Symptom** (Compose logs):  
  `FATAL: database files are incompatible with server` /  
  `DETAIL: The data directory was initialized by PostgreSQL version 14, not compatible with 15.14.`
- **Root cause**: an existing local volume was created by v14; Compose later pulled v15.14 for `db`.
- **AI‑guided options**:
  - **Option A**: keep v15, **dump & restore** (pg_dump/pg_restore) or **destroy** the local volume.
  - **Option B**: **pin the image to 14** to match the existing on‑disk catalog.
- **Action taken**: pin to `postgres:14` (faster), or `docker compose down -v` to wipe local data when safe.
- **Outcome**: DB container became healthy; backend booted without `ECONNREFUSED` retry loops.

```yaml
# docker-compose.yml (excerpt)
services:
  db:
    image: postgres:14
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d app"]
      interval: 5s
      timeout: 3s
      retries: 20
```

### 3.2 Dashboard serving (StaticFiles in dev, redirect in Docker)
- **Initial attempt**: mount `StaticFiles(directory="frontend")` and return `FileResponse("frontend/index.html")` from `/api/dashboard`.
- **Failure mode in Docker**: backend image **did not include** `frontend/`, causing file‑not‑found errors and container crashes.
- **AI‑suggested fix**: *dual‑mode handler* — serve files in dev; **redirect** to `/dashboard.html` (served by NGINX) in Docker.
- **Result**: stable containers; cleaner separation of concerns.

```python
# backend/main.py (pattern)
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

if os.getenv("RUN_ENV") == "docker":
    @app.get("/api/dashboard", include_in_schema=False)
    def dashboard():
        return RedirectResponse("/dashboard.html", status_code=302)
else:
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

    @app.get("/api/dashboard", include_in_schema=False)
    def dashboard():
        return FileResponse("frontend/index.html")
```

### 3.3 CamelCase vs snake_case broke UI score display
- **Symptom**: the table showed “—” for health; detail view failed or looked empty.
- **Root cause**: the frontend expected `healthScore` and factor keys in **camelCase**, while Pydantic models emitted `snake_case`.
- **AI‑guided fix**: standardize response shape using Pydantic v2 **aliases** and dump with `by_alias=True`:
  
```python
# backend/schemas.py (Pydantic v2)
from pydantic import BaseModel, Field
from pydantic import ConfigDict

def to_camel(s: str) -> str:
    parts = s.split('_')
    return parts[0] + ''.join(p.title() for p in parts[1:])

class HealthOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    health_score: float = Field(alias="healthScore")
    login_score: float
    feature_adoption_score: float
    support_tickets_score: float
    invoice_timeliness_score: float
    api_trend_score: float

# When returning:
return health_out.model_dump(by_alias=True)
```
- **Outcome**: the **score chip** updated correctly; factor bars rendered consistently.

### 3.4 DB connectivity when using `localhost` from containers
- **Symptom**: backend couldn’t reach Postgres: connection refused.
- **Root cause**: using `localhost` inside the backend container; the DB is accessible via Compose DNS name (**`db`**), not the host loopback.
- **AI‑guided fix**: construct `DATABASE_URL` with `db:5432` (or env vars) and ensure `depends_on: service_healthy`.
- **Outcome**: stable startup without retry storms.

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/app
```

### 3.5 Pydantic v2 deprecation warnings
- **Symptom** (pytest): `PydanticDeprecatedSince20: class-based config is deprecated; use ConfigDict`.
- **AI‑guided fix**: migrate `class Config` → `model_config = ConfigDict(...)`; optionally filter warnings in tests until migration is complete.
- **Outcome**: cleaner test output; future‑proof models.

```python
from pydantic import BaseModel, ConfigDict

class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # v2 style
```

### 3.6 Coverage understanding and scope
- **Symptom**: `schemas.py`/`models.py` appeared 100% covered without direct tests (import‑time execution).  
- **AI‑guided fix**: keep threshold at **≥80%**, focus on **health logic** + **API** tests; optionally exclude boilerplate with `.coveragerc`:
  
```ini
# .coveragerc
[run]
omit =
    backend/db/*
    backend/migrations/*
    backend/__init__.py
```

### 3.7 NGINX proxying for same‑origin API calls
- **Issue**: CORS friction and mixed dev/prod URLs.  
- **AI‑guided solution**: proxy `/api/*` to backend from NGINX so the UI calls same‑origin:

```nginx
upstream backend_api { server backend:8000; }

server {
  listen 80;
  root /usr/share/nginx/html;
  index home.html index.html;

  location /api/ {
    proxy_pass http://backend_api;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }

  location = /app { try_files /home.html =404; }
  location = /api/dashboard { try_files /dashboard.html =404; }
}
```

### 3.8 Factor edge cases and smoothing
- **Iteration**: defined **neutral** invoice score (50) when no history; set **0/0 → 50** for API trend;
  capped login normalization (e.g., 20 logins → 100).  
- **Tests**: unit tests added for bounds, caps, neutral cases, and monotonicity; integration tests to
  confirm that posting an event modifies the score as expected.

```python
# Example: API trend scorer (30d vs prev 30d)
def api_trend_score(curr: int, prev: int) -> float:
    if curr == 0 and prev == 0:
        return 50.0
    if prev == 0:
        return 100.0
    change = (curr - prev) / prev
    # map change in [-1, +∞) to [0,100] with gentle saturation
    raw = 50 + 50 * max(-1.0, min(1.0, change))
    return max(0.0, min(100.0, raw))
```

### 3.9 Dashboard wiring & UI correctness
- **Issue**: the score chip initially attempted to read from the list row (which didn’t include a precomputed score).  
- **Fix**: set the chip from the `/health` response in the detail fetch; align key names with camelCase.
- **Outcome**: accurate live score display and consistent factor bars.

```js
// after fetching /api/customers/{id}/health
chip.textContent = data.healthScore.toFixed(1);
renderBars(data); // loginScore, featureAdoptionScore, etc.
```

---

## 4) Artifacts & How to Verify

- **Docker/Compose**: `db` with healthcheck, `backend` with depends_on and `DATABASE_URL`, `frontend` (NGINX) proxying `/api/*`.
- **Entrypoint**: waits for DB, optional seed, starts Uvicorn; `/openapi.json` as health endpoint.
- **Seed**: 50–100 customers, ~90 days of events; invoices mix on‑time/late; features used across customers.
- **Health logic**: five factor scorers, smoothed edge cases, weighted average; documented windows (30/90 days).
- **API**: `GET /api/customers`, `GET /api/customers/{id}/health`, `POST /api/customers/{id}/events`.
- **Tests**: unit (factors) + integration (routes, 404, 422, mutation); coverage ≥80% via `pytest.ini`.
- **Dashboard**: table → detail with factor bars and score chip; accessible colors/labels.
- **Deployment**: local `docker compose up --build`; optional cloud on Render/Railway with managed Postgres.

---

## 5) Summary

Across the three development threads, AI assistance provided **research**, **design scaffolding**, and **hands‑on fixes**.
The collaboration produced a system that is **operationally solid** (healthchecks, redirects, proxying), **analytically credible** (realistic
seeding and principled scoring), and **verifiable** (tests + coverage). The iterations documented above show a clear
trajectory from draft → robust prototype with production‑leaning practices.
