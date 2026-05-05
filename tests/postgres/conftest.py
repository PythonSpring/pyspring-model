import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_container():
    """Start a PostgreSQL container once per test session."""
    pg = PostgresContainer("postgres:16-alpine")
    pg.start()
    yield pg
    pg.stop()


@pytest.fixture(autouse=True)
def db_engine(request, pg_container):
    """Create a fresh database per test to avoid DDL lock contention."""
    admin_url = pg_container.get_connection_url()
    admin_engine = create_engine(admin_url, poolclass=NullPool, isolation_level="AUTOCOMMIT")

    db_name = f"test_{uuid.uuid4().hex[:12]}"
    with admin_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name}"))
    admin_engine.dispose()

    test_url = admin_url.rsplit("/", 1)[0] + f"/{db_name}"
    engine = create_engine(test_url, echo=False, poolclass=NullPool)

    if request.instance is not None:
        request.instance.engine = engine
    yield engine

    engine.dispose()
    admin_engine = create_engine(admin_url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"
        ))
        conn.execute(text(f"DROP DATABASE {db_name}"))
    admin_engine.dispose()
