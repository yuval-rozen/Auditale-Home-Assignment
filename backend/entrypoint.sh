#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for Postgres to accept TCP connections..."
python - <<'PY'
import os, re, socket, time, sys
url = os.environ.get("DATABASE_URL", "")
m = re.match(r".*://[^:]+:[^@]+@([^:/]+):(\d+)/", url)
if not m:
    print("Invalid DATABASE_URL:", url); sys.exit(1)
host, port = m.group(1), int(m.group(2))
for i in range(60):
    try:
        with socket.create_connection((host, port), timeout=1.5):
            print("DB is up"); break
    except OSError:
        print("...still waiting"); time.sleep(1)
else:
    print("Gave up waiting for DB"); sys.exit(1)
PY

echo "Creating tables (if needed) and seeding (if empty)..."
# The seed script will create tables and skip reseeding if data already exists.
python db/seed.py --customers 80

echo "Starting API..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
