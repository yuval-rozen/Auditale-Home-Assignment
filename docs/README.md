# Customer Health App

## Introduction

The **Customer Health App** is a demo SaaS application that simulates customer activity and calculates a **Customer Health Score**.

It demonstrates:
- Synthetic but **realistic customer data generation** (`db/seed.py`).
- **Health scoring methodology** based on engagement, adoption, support, billing, and usage trends.
- **Full-stack architecture**:
  - **Frontend**: Nginx serving static HTML dashboards.
  - **Backend**: FastAPI service exposing APIs for ingest and health scoring.
  - **Database**: PostgreSQL, seeded with correlated customer behaviors.
- **Containerized deployment** with Docker Compose.

---

## Prerequisites

You will need:

- **Python 3.10+** (for local testing)
- **Docker & Docker Compose** (for running services)
- **PostgreSQL 14+** (used in production; local dev uses Dockerized Postgres)

Dependencies are defined in [`requirements.txt`](requirements.txt).

---

## Setup Instructions

## Installation

### Clone the Repository
```bash
git clone https://github.com/yuval-rozen/Auditale-Home-Assignment.git
cd Auditale-Home-Assignment
```

## Configuration

- **Environment Variables:**  
  The backend expects `DATABASE_URL` in the form:
  ```
  postgres://user:password@db:5432/customer_health
  ```
- All these defaults are set in `docker-compose.yml`.
- Secrets and DB credentials should be provided via a `.env` file or environment variables.

---

## Deployment Guide (Production)

1. **Build and start containers**:
   ```bash
   docker compose up --build
   ```

2. **Wait for services**:  
   The `entrypoint.sh` script waits for Postgres, runs migrations & seeding (`db/seed.py`), then starts FastAPI.

3. **Access the app**:
  - Frontend: [http://localhost:8080/home.html](http://localhost:8080/home.html)
  - Dashboard: [http://localhost:8080/dashboard.html](http://localhost:8080/dashboard.html)
  - API Docs: [http://localhost:8080/docs](http://localhost:8080/docs)

4. **Seed Data**: By default, ~80 customers are generated with realistic personas, 90 days of events, and invoices.

---

### Install Python Dependencies (optional, for running backend locally)
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

---

## Usage

### Example: Get All Customers
```bash
curl http://localhost:8080/api/customers
```

### Example: Get Health Score for a Customer
```bash
curl http://localhost:8080/api/customers/1/health
```

The response includes factors and final score.

---

## Project Structure

Is detailed on `Arcitecture.md`

---

## Tests
Run the test suite using the npm script:
```bash
npm test
```
- With coverage and thresholds (`pytest.ini` enforces 80% coverage):
  ```
- Tests use **SQLite** (file-backed) for isolation (`conftest.py`).

---

## Troubleshooting

- **Database fails to start**: Ensure no leftover volume from a different Postgres version. Remove with:
  ```bash
  docker volume ls
  ```
- look for anything named like Auditale-Home-Assignment* or pgdata and remove if needed: docker volume rm <the_volume_name>
- **Port conflicts**: Check if ports `8080` (frontend) or `5432` (Postgres) are in use.
- **Tests failing**: Ensure virtualenv is active and dependencies installed.

---

## Support

For any issues please contact me via [mail](yuval99.yr@gmail.com).

**Have A Nice Day! :)**


## Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/)
- [PostgreSQL](https://www.postgresql.org/)
- [Docker](https://www.docker.com/)
- [Faker](https://faker.readthedocs.io/en/master/) for data generation. 

