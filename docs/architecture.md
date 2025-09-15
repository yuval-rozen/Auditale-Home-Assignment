# Customer Health App — Architecture Document

## 1) Overview

**Purpose.** The Customer Health App is a containerized SaaS project that computes and visualizes customer health scores. 
It provides a static **Nginx** frontend, a **FastAPI** backend for RESTful services, and a **Postgres** database for persistent storage. 
Local orchestration is managed with **Docker Compose**.

**Tech stack.**
- **Frontend:** Nginx serving static HTML/CSS/JS and proxying API requests.
- **Backend:** FastAPI application (Python) exposing endpoints for events, invoices, feature usage, and health scoring.
- **Database:** Postgres, seeded with realistic synthetic data.
- **Orchestration:** Docker Compose builds and networks the three services for local development and demos.

## 2) System Architecture

Two complementary diagrams illustrate the system design are in the 'system architecture diagrams' folder:

**Detailed service ↔ files mapping**
**High-level runtime view (in Docker network)**

### Runtime interactions
1. **Browser → Frontend (Nginx)** over **HTTP** to fetch static pages and assets.
2. **Frontend → Backend (FastAPI)** via **HTTP** for API requests (e.g., login/API events, invoices, health scores).
3. **Backend → Database (Postgres)** via **SQL** (SQLAlchemy models/queries) to read/write domain data.
4. All services run in **Docker containers**, attached to a shared **Docker network**, enabling service-to-service DNS and isolated connectivity.

## 3) Component Breakdown

### 3.1 Frontend (Nginx)
**Location:** `/frontend`  
**Files:**
- `home.html` — Landing page that introduces the product and links to the dashboard.
- `dashboard.html` — Health dashboard; issues API calls (via the Nginx proxy) to fetch computed scores and recent activity.
- `nginx.conf` — Server configuration: serves static files and proxies matching paths to the backend service.
- `assets/` — Static images and media (`assets/home-hero.jpg`).
- `Dockerfile` — Builds the Nginx image that serves the above assets.

**Responsibilities:**
- Serve static content efficiently.
- Terminate HTTP for the browser.
- Forward API requests to the backend via an internal hostname (`localhost:8000`) on the Docker network.

### 3.2 Backend (FastAPI)
**Location:** `/backend`  
**Files:**
- `main.py` — Application entrypoint, router registration, and app lifecycle.
- `models.py` — SQLAlchemy ORM models (e.g., Customer, Event, Invoice, SupportTicket, FeatureUsage).
- `schemas.py` — Pydantic models for request/response validation.
- `services/health.py` — Health scoring utilities (scoring factors, weighting, and final score computation).
- `tests/` — Unit and integration tests for endpoints and scoring logic.
- `Dockerfile` — Container image for the FastAPI app.
- `requirements.txt` — Python dependencies.
- `entrypoint.sh` — Container startup script (e.g., running uvicorn, migration hooks).

**Responsibilities:**
- Expose REST endpoints for ingesting events, computing scores, and serving customer data to the dashboard.
- Implement domain logic: scoring factors (login frequency, feature adoption, support load, invoice timeliness, API trend) and weighted health score.
- Interact with Postgres using SQLAlchemy sessions and models.

### 3.3 Database (Postgres)
**Location:** `/db`  
**Files:**
- `seed.py` — Seeds the database with synthetic, correlated data (90 days of activity + several billing cycles) to support demos, tests, and local development.

**Responsibilities:**
- Persist customers, events, invoices, feature usage, and support tickets.
- Provide the system of record for the backend queries.

### 3.4 Project Root
**Location:** project root  
**Files:**
- `docker-compose.yml` — Orchestrates services, networks, and volumes; defines build contexts and service dependencies.
- `docs/` — Centralized documentation repository and `README.md`. It serves as the reference hub for both technical design and process transparency.
- `pytest.ini` — Pytest configuration for backend tests.
- `package.json` — Optional metadata/scripts (e.g., frontend utilities or dev tooling).

## 4) Data Flow (End-to-End)

1. **Open Home**
   - The user navigates to `/home.html` in the **browser**.
   - **Nginx** serves `home.html` and its assets directly from the container.

2. **Navigate to Dashboard**
   - The user clicks **Dashboard** (link to `/dashboard.html`).
   - The **browser** loads `dashboard.html`; client-side code triggers API requests (`/api/customers/{id}/health`).

3. **Frontend → Backend**
   - **Nginx** proxies `/api/...` calls to the **FastAPI** service (container hostname `backend` inside the Docker network).

4. **Backend → Database**
   - **FastAPI** handlers use SQLAlchemy to query **Postgres** for events, invoices, features, and tickets.
   - The backend runs health scoring logic and assembles a JSON response.

5. **Response Assembly**
   - Backend returns JSON to **Nginx**, which returns it to the **browser**.
   - The dashboard renders updated metrics, charts, and the overall health score.

## 5) Deployment & Environment

- **Docker Compose** builds three images (frontend, backend, database) and attaches them to a single **Docker network**.
- The Compose file exposes the Nginx port on localhost (`http://localhost:8080`) and the backend port.
- **Volumes** saves Postgres data during development.

## 6) Appendix — File Tree (reference)

```
C:\Users\yuval\customer-health-app>
¦   docker-compose.yml
¦   package.json
¦   pytest.ini
¦          
+---docs
¦   ¦   README.md
¦   ¦   Health_Score_Methodology.md
¦   ¦   Architecture.md
¦   ¦   Sample_Api_Responses.md
¦   ¦   AI_Collaboration_Evidence.md
¦          
+---backend
¦   ¦   db.py
¦   ¦   Dockerfile
¦   ¦   entrypoint.sh
¦   ¦   main.py
¦   ¦   models.py
¦   ¦   requirements.txt
¦   ¦   schemas.py
¦   ¦   __init__.py
¦   ¦   
¦   +---services
¦   ¦   ¦   health.py
¦   ¦   ¦               
¦   +---tests
¦   ¦   ¦   conftest.py
¦   ¦   ¦   test_api_integration.py
¦   ¦   ¦   test_health_unit.py
¦   ¦   ¦                           
+---db
¦    ¦  seed.py
¦    ¦          
+---frontend
    ¦   dashboard.html
    ¦   Dockerfile
    ¦   home.html
    ¦   nginx.conf
    ¦   
    +---assets
            home-hero.jpg
```

