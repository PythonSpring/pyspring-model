import pytest
from sqlalchemy import create_engine
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
    """Provide a PostgreSQL engine for each test method."""
    engine = create_engine(pg_container.get_connection_url(), echo=False)
    if request.instance is not None:
        request.instance.engine = engine
    yield engine
    engine.dispose()
