# AI Collaboration Evidence

This document summarizes how AI tools were used throughout the project, the quality of research and implementation decisions they informed, and concrete evidence of iteration on AI-generated suggestions.

---

## 1) Documentation of AI Tool Usage

### Architecture, API & Factor Design
- Defined the core endpoints (`/api/customers`, `/api/customers/{id}/health`, `/api/customers/{id}/events`) and a dev dashboard route (`/api/dashboard`). Clarified factor windows (30/90 days), neutral behavior for missing invoices, and weighting strategy. 

### Docker/Compose & Entrypoint
- Introduced a robust compose file with a Postgres healthcheck, backend `depends_on` readiness, and a backend entrypoint that waits for DB, optionally seeds, then starts Uvicorn. Frontend served by NGINX; backend healthcheck on `/openapi.json`.

### Seeding Strategy & Validation
- Recommended seeding 50–100 customers with ~90 days of multi-table activity; verified large event counts as proof of realistic data volumes.

### Testing Strategy
- Delivered unit tests for each factor and integration tests covering success, `404`, and `422` paths, plus coverage configuration (≥80%). Explained why models/schemas show high coverage due to import execution.

### Dashboard Implementation
- Provided a minimal no-build HTML/JS dashboard that lists customers and shows a health breakdown with factor bars on row click; supplied FastAPI snippet to serve `/api/dashboard` in dev and a redirect-based approach for Dockerized environments.

---

## 2) Quality of Research & Implementation Decisions

- **Health methodology**: codified five factors with industry-aligned windows and normalization rules (caps, monotonicity, smoothing). Weighted average emphasizes engagement/adoption while keeping billing and API trend meaningful.
- **Neutral defaults**: invoice factor returns 50 when no history (avoids penalizing new customers).
- **Seed realism**: large, varied dataset ensures distributions across Healthy/At‑risk/Churn‑risk and produces meaningful factor scores.
- **Operational polish**: compose healthchecks, one-command test runs, coverage thresholds, and a simple deployment path to a cloud runtime for visibility.

---

## 3) Evidence of Iterating on AI Suggestions

### a) Frontend Score Display
- Initial UI set the score chip from the list row (which lacked a precomputed score), resulting in “—”. Iteration updated the detail view to set the chip from `/health` response and aligned field names (camelCase vs snake_case).

### b) Dashboard Serving Strategy
- Early approach mounted `StaticFiles("frontend")` in the backend image. In Docker, that folder didn’t exist in the backend container, causing crashes. Iteration switched to a redirect-based handler in Docker (serve files locally in dev; redirect to NGINX in containers).

### c) Coverage Understanding & Configuration
- Clarified why `models.py` and `schemas.py` appeared as 100% covered via import-time execution. Options provided to narrow coverage to “hard logic” or omit boilerplate via `.coveragerc` while still exceeding the 80% threshold.

### d) Compose & DB Connectivity
- Resolved mistakes like connecting to `localhost` from the backend container and Postgres role/password mismatches by standardizing env vars, adding healthchecks, and using service-name DNS (`db`) in `DATABASE_URL` construction.

---

## 4) How AI Guidance Was Applied in Code/Config

- **Compose & Entrypoint**: adopted healthcheck, DB wait loop, seeding flags, and container health configuration.
- **Health Service**: implemented factor scorers with caps, monotonicity, smoothing, and neutral‑when‑no‑history invoice scoring; aggregated by weights.
- **Tests**: added edge‑case unit tests and integration tests asserting `404`/`422`, post‑event changes, and factor ranges; enforced coverage ≥80% via `pytest.ini`.
- **Dashboard**: shipped a no‑build HTML/JS dashboard first (fast acceptance), with a clear upgrade path to React.

---

## 5) What Changed Because of AI Feedback (Quick List)

- Introduced DB healthchecks & `depends_on: service_healthy`.
- Implemented on‑start seeding toggled by env flags.
- Fixed dashboard score display to use `/health` response.
- Swapped backend static serving → redirect in Docker to prevent crashes.
- Clarified coverage semantics; added options to tailor scope.
- Documented deployment playbook (Render/Railway) and repo acceptance checklist.

---

## 6) Artifacts for Reviewers

- **Compose + Dockerfiles** – db, backend, and frontend wired with health and ports.
- **Seed Script** – generates realistic multi‑table activity over ~90 days.
- **Health Module** – well‑documented factor scoring + weights + aggregator.
- **Tests** – unit + integration with one‑command run and coverage threshold.
- **Dashboard** – minimal UI hitting real endpoints; upgrade path to React.
- **Docs** – README, health methodology, deployment guide, and this evidence file.