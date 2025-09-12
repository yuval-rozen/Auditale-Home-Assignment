"""
conftest.py
------------
Pytest fixtures for FastAPI + SQLAlchemy tests.

Goals:
- Provide a fast, isolated test database (SQLite) that does NOT touch the real Postgres.
- Override the app's `get_db` dependency so API tests use the test Session.
- Create tables once per test session, and clean rows between tests.

Why SQLite (file) and not in-memory?
- FastAPI's TestClient may run requests in different threads.
- SQLite in-memory DB is process-local *and* connection-local; different connections
  would see different (empty) DBs.
- Using a temporary **file-backed** SQLite database gives us:
  - one physical DB visible to all connections in the test process,
  - good speed,
  - no external services required (no Docker/Postgres needed for unit/integration tests).

Fixture scopes:
- `test_engine_dbfile`: session-scoped temp file path; removed at the end.
- `test_engine`: session-scoped SQLAlchemy Engine bound to that file; creates tables once.
- `db_session`: function-scoped Session; cleans all tables between tests.
- `client`: function-scoped FastAPI TestClient with `get_db` dependency overridden to use `db_session`.
"""

import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Ensure project root is on sys.path so `import backend.*` works during pytest collection
import os, sys
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


# Import the app and ORM metadata so we can:
# - create tables on the test engine
# - override the app's DB dependency
from backend.main import app
from backend.db import Base
from backend.models import Customer, Event, Invoice, SupportTicket, FeatureUsage


@pytest.fixture(scope="session")
def test_engine_dbfile():
    """
    Create a temporary SQLite **file** and return its path.

    We deliberately choose a *file-backed* SQLite DB (not `:memory:`) to avoid
    threading/connection visibility issues during tests.

    Yields:
        str: Absolute path to the temporary .db file.

    Cleanup:
        Attempts to remove the file at the end of the test session.
        (If something still has the file open on Windows, removal may be deferred.)
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)  # close the OS-level handle; SQLAlchemy will manage connections
    yield path


@pytest.fixture(scope="session")
def test_engine(test_engine_dbfile):
    """
    Create a SQLAlchemy Engine bound to the temporary SQLite database file.

    - `check_same_thread=False` allows the same connection to be used across threads,
      which the TestClient may do under the hood.
    - `Base.metadata.create_all` creates tables once for the entire test session.

    Yields:
        sqlalchemy.engine.Engine: Engine connected to the test SQLite DB.
    """
    engine = create_engine(
        f"sqlite:///{test_engine_dbfile}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    # Create all ORM tables once per session (fast and sufficient for tests)
    Base.metadata.create_all(bind=engine)
    yield engine

    # --- Teardown in correct order for Windows ---
    engine.dispose()  # release file handle
    try:
        os.remove(test_engine_dbfile)
    except FileNotFoundError:
        pass


@pytest.fixture(scope="function")
def db_session(test_engine):
    """
    Provide a fresh SQLAlchemy Session for each test function.

    Behavior:
    - Yields a Session bound to the shared test Engine.
    - After the test, closes the Session and deletes all rows from all tables,
      ensuring tests are isolated and order-independent.

    Notes:
    - We delete rows in **reverse dependency order** (`reversed(Base.metadata.sorted_tables)`)
      so child tables are cleared before parent tables, avoiding FK constraint issues.
    """
    TestingSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Clean all tables between tests (keeps schema, wipes data)
        for tbl in reversed(Base.metadata.sorted_tables):
            session.execute(tbl.delete())
        session.commit()


@pytest.fixture(scope="function")
def client(db_session):
    """
    FastAPI TestClient that uses the test Session instead of the real database.

    How it works:
    - Overrides the app's `get_db` dependency to yield our `db_session`.
    - Any request made via this client will use the SQLite test DB.
    - After the test, dependency overrides are cleared.

    Usage in tests:
        def test_something(client, db_session):
            # Arrange: write directly with db_session
            # Act: call endpoints with client
            # Assert: verify responses and/or DB state

    Returns:
        TestClient: A context-managed client bound to the app with the DB override.
    """
    from backend.db import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            # Nothing special to close here; db_session is closed in its fixture
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    # Ensure we leave the app in a clean state for subsequent tests
    app.dependency_overrides.clear()
