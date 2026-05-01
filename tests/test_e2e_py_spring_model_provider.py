"""
E2E tests for PySpringModelProvider lifecycle with SQLite and PostgreSQL backends.

Verifies the full starter lifecycle:
  on_configure -> IoC container build -> on_initialized -> table creation -> CRUD
"""

import json
import os
import tempfile
from typing import Optional

import pytest
from sqlmodel import Field

from py_spring_model import CrudRepository, PySpringModel, PySpringModelProvider


# ---------------------------------------------------------------------------
# Test models & repositories
# ---------------------------------------------------------------------------

class Item(PySpringModel, table=True):
    __tablename__ = "e2e_item"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    quantity: int = 0


class ItemRepository(CrudRepository[int, Item]):
    ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_app_fixture(db_uri: str):
    """Create a temporary directory with config files for PySpringApplication."""
    tmpdir = tempfile.mkdtemp()
    src_dir = os.path.join(tmpdir, "src")
    os.makedirs(src_dir, exist_ok=True)

    # Write a minimal placeholder so the scanner doesn't complain
    with open(os.path.join(src_dir, "__init__.py"), "w") as f:
        f.write("")

    app_config = {
        "app_src_target_dir": src_dir,
        "server_config": {"host": "0.0.0.0", "port": 8080, "enabled": False},
        "properties_file_path": os.path.join(tmpdir, "application-properties.json"),
        "loguru_config": {"log_file_path": "", "log_level": "DEBUG"},
        "shutdown_config": {"timeout_seconds": 5.0, "enabled": False},
    }

    app_properties = {
        "py_spring_model": {
            "sqlalchemy_database_uri": db_uri,
            "create_all_tables": True,
        }
    }

    config_path = os.path.join(tmpdir, "app-config.json")
    with open(config_path, "w") as f:
        json.dump(app_config, f)

    with open(app_config["properties_file_path"], "w") as f:
        json.dump(app_properties, f)

    return config_path


def _run_app(config_path: str):
    """Run the PySpring application with PySpringModelProvider."""
    from py_spring_core import PySpringApplication

    app = PySpringApplication(
        config_path,
        starters=[PySpringModelProvider()],
    )
    app.run()
    return app


# ---------------------------------------------------------------------------
# SQLite E2E tests
# ---------------------------------------------------------------------------

class TestPySpringModelProviderSQLite:
    """E2E tests using SQLite in-memory database."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.db_path = str(tmp_path / "test.db")
        self.db_uri = f"sqlite:///{self.db_path}"
        self.config_path = _create_app_fixture(self.db_uri)
        self.app = _run_app(self.config_path)
        yield
        # cleanup: reset global state
        PySpringModel._engine = None
        PySpringModel._metadata = None
        PySpringModel._connection = None

    def test_on_configure_registers_entities(self):
        """Starter's on_configure should have registered component, properties, and controller classes."""
        starter = self.app.starters[0]
        assert isinstance(starter, PySpringModelProvider)

        from py_spring_model.core.commons import PySpringModelProperties
        from py_spring_model.py_spring_model_rest import PySpringModelRestService
        from py_spring_model.py_spring_model_rest.controller.session_controller import SessionController

        assert PySpringModelProperties in starter.properties_classes
        assert PySpringModelRestService in starter.component_classes
        assert SessionController in starter.rest_controller_classes

    def test_on_initialized_creates_engine(self):
        """After on_initialized, the starter should have a live SQLAlchemy engine."""
        starter = self.app.starters[0]
        assert hasattr(starter, "sql_engine")
        assert starter.sql_engine is not None
        assert str(starter.sql_engine.url).startswith("sqlite")

    def test_tables_created(self):
        """on_initialized with create_all_tables=True should create the e2e_item table."""
        from sqlalchemy import inspect as sa_inspect

        starter = self.app.starters[0]
        inspector = sa_inspect(starter.sql_engine)
        table_names = inspector.get_table_names()
        assert "e2e_item" in table_names

    def test_crud_operations(self):
        """Full CRUD cycle through the framework-initialized repository."""
        repo = ItemRepository()

        # Create
        item = Item(name="Widget", quantity=10)
        repo.save(item)
        assert item.id is not None

        # Read
        found = repo.find_by_id(item.id)
        assert found is not None
        assert found.name == "Widget"
        assert found.quantity == 10

        # Update
        found.quantity = 20
        repo.save(found)
        updated = repo.find_by_id(item.id)
        assert updated is not None
        assert updated.quantity == 20

        # Delete
        assert repo.delete_by_id(item.id)
        assert repo.find_by_id(item.id) is None

    def test_find_all(self):
        """Bulk insert and find_all should work through the framework lifecycle."""
        repo = ItemRepository()
        repo.save(Item(name="A", quantity=1))
        repo.save(Item(name="B", quantity=2))

        items = repo.find_all()
        assert len(items) == 2
        names = {i.name for i in items}
        assert names == {"A", "B"}

    def test_app_context_set_on_starter(self):
        """The framework should have set app_context on the starter."""
        starter = self.app.starters[0]
        assert starter.app_context is not None


# ---------------------------------------------------------------------------
# PostgreSQL E2E tests (testcontainers)
# ---------------------------------------------------------------------------

class TestPySpringModelProviderPostgres:
    """E2E tests using PostgreSQL via testcontainers."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from testcontainers.postgres import PostgresContainer

        self.pg = PostgresContainer("postgres:16-alpine")
        self.pg.start()
        db_uri = self.pg.get_connection_url()
        self.config_path = _create_app_fixture(db_uri)
        self.app = _run_app(self.config_path)
        yield
        PySpringModel._engine = None
        PySpringModel._metadata = None
        PySpringModel._connection = None
        self.pg.stop()

    def test_on_initialized_creates_engine_postgres(self):
        """After on_initialized, engine URL should point to PostgreSQL."""
        starter = self.app.starters[0]
        assert hasattr(starter, "sql_engine")
        assert "postgresql" in str(starter.sql_engine.url)

    def test_tables_created_postgres(self):
        """Tables should be created in PostgreSQL."""
        from sqlalchemy import inspect as sa_inspect

        starter = self.app.starters[0]
        inspector = sa_inspect(starter.sql_engine)
        table_names = inspector.get_table_names()
        assert "e2e_item" in table_names

    def test_crud_operations_postgres(self):
        """Full CRUD cycle against PostgreSQL."""
        repo = ItemRepository()

        # Create
        item = Item(name="Gadget", quantity=5)
        repo.save(item)
        assert item.id is not None

        # Read
        found = repo.find_by_id(item.id)
        assert found is not None
        assert found.name == "Gadget"
        assert found.quantity == 5

        # Update
        found.quantity = 50
        repo.save(found)
        updated = repo.find_by_id(item.id)
        assert updated is not None
        assert updated.quantity == 50

        # Delete
        assert repo.delete_by_id(item.id)
        assert repo.find_by_id(item.id) is None

    def test_find_all_postgres(self):
        """Bulk insert and find_all against PostgreSQL."""
        repo = ItemRepository()
        repo.save(Item(name="X", quantity=10))
        repo.save(Item(name="Y", quantity=20))

        items = repo.find_all()
        assert len(items) == 2
        names = {i.name for i in items}
        assert names == {"X", "Y"}

    def test_app_context_set_on_starter_postgres(self):
        """The framework should have set app_context on the starter."""
        starter = self.app.starters[0]
        assert starter.app_context is not None
