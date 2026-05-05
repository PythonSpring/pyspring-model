import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def db_engine(request):
    """Provide a fresh SQLite in-memory engine for each test method."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if request.instance is not None:
        request.instance.engine = engine
    yield engine
    engine.dispose()
