FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

# OS deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source
COPY backend /app/backend
COPY db /app/db
COPY backend/entrypoint.sh /app/entrypoint.sh
COPY backend/tests /app/tests
COPY pytest.ini /app/pytest.ini

# Fix Windows CRLF if present and make executable
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
