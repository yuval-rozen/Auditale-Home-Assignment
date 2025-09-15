## Deployment Evidence (Option A — Docker Compose)

### How I ran it
- Prereqs: Docker Desktop
- Start: `docker compose up --build`
- Frontend: http://localhost:8080/home.html
- Dashboard: http://localhost:8080/dashboard.html
- API base: http://localhost:8000
- API docs: http://localhost:8000/docs (and proxyed to http://localhost:8080/docs)
- Tests: `npm test` (runs pytest in a one-off backend container, ≥80% coverage)

### Screenshots included
1) Docker Desktop/terminal showing 3 containers running (db, backend, frontend)
2) Home page (`/home.html`) in the browser
3) Dashboard (`/dashboard.html`)
4) FastAPI docs (`/docs`)
5) Terminal: `npm test` summary with coverage

### One sample API responses (from localhost), see all examples on screenshots/

**List customers (200 OK)**
```bash
curl -X 'GET' \
  'http://localhost:8080/api/customers' \
  -H 'accept: application/json'
  ```

200 Successful Response

Response headers:
connection: keep-alive
content-length: 5996
content-type: application/json
date: Mon,15 Sep 2025 06:48:33 GMT
server: nginx/1.29.1

Response body
...
[
{
"id": 17,
"name": "Nguyen-Lopez",
"segment": "SMB",
"health_score": 25
},
{
"id": 16,
"name": "Franco-Huffman",
"segment": "SMB",
"health_score": 80.6
},
{
"id": 18,
"name": "Maldonado-Baker",
"segment": "enterprise",
"health_score": 63.8
},
{
"id": 19,
"name": "Jordan and Sons",
"segment": "SMB",
"health_score": 59.5
}
]
...
