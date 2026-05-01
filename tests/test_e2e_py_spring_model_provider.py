"""
E2E tests for PySpringModelProvider lifecycle with SQLite and PostgreSQL backends.

Verifies the full starter lifecycle:
  on_configure -> IoC container build -> on_initialized -> table creation -> CRUD
"""

import json
import os
import shutil
import tempfile
from typing import Optional

import pytest
from sqlmodel import Field, SQLModel

from py_spring_model import CrudRepository, PySpringModel, PySpringModelProvider
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.repository.repository_base import RepositoryBase


# ---------------------------------------------------------------------------
# Test models & repositories
# ---------------------------------------------------------------------------

class Item(PySpringModel, table=True):
    __tablename__ = "e2e_item"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    quantity: int = 0


class Category(PySpringModel, table=True):
    __tablename__ = "e2e_category"
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str


class ItemRepository(CrudRepository[int, Item]):
    ...


class CategoryRepository(CrudRepository[int, Category]):
    ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_app_fixture(db_uri: str, create_all_tables: bool = True):
    """Create a temporary directory with config files for PySpringApplication."""
    tmpdir = tempfile.mkdtemp()
    src_dir = os.path.join(tmpdir, "src")
    os.makedirs(src_dir, exist_ok=True)

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
            "create_all_tables": create_all_tables,
        }
    }

    config_path = os.path.join(tmpdir, "app-config.json")
    with open(config_path, "w") as f:
        json.dump(app_config, f)

    with open(app_config["properties_file_path"], "w") as f:
        json.dump(app_properties, f)

    return config_path, tmpdir


def _run_app(config_path: str):
    """Run the PySpring application with PySpringModelProvider."""
    from py_spring_core import PySpringApplication

    app = PySpringApplication(
        config_path,
        starters=[PySpringModelProvider()],
    )
    app.run()
    return app


def _cleanup(tmpdir: str):
    """Reset all global state that PySpringModelProvider sets."""
    SessionContextHolder.clear_session()

    # Close RepositoryBase connection before resetting
    if RepositoryBase.connection is not None:
        try:
            RepositoryBase.connection.close()
        except Exception:
            pass
    RepositoryBase.engine = None
    RepositoryBase.connection = None

    PySpringModel._engine = None
    PySpringModel._metadata = None
    PySpringModel._connection = None
    PySpringModel._models = None

    shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# SQLite E2E tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestPySpringModelProviderSQLite:
    """E2E tests using SQLite file database."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.db_path = str(tmp_path / "test.db")
        self.db_uri = f"sqlite:///{self.db_path}"
        self.config_path, self.tmpdir = _create_app_fixture(self.db_uri)
        self.app = _run_app(self.config_path)
        yield
        _cleanup(self.tmpdir)

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
# SQLite edge-case tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestPySpringModelProviderEdgeCases:
    """Edge-case tests using SQLite."""

    def test_create_all_tables_false_skips_table_creation(self, tmp_path):
        """When create_all_tables=False, tables should NOT be created."""
        db_path = str(tmp_path / "no_tables.db")
        db_uri = f"sqlite:///{db_path}"
        config_path, tmpdir = _create_app_fixture(db_uri, create_all_tables=False)
        try:
            app = _run_app(config_path)
            starter = app.starters[0]

            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(starter.sql_engine)
            table_names = inspector.get_table_names()
            assert "e2e_item" not in table_names
            assert "e2e_category" not in table_names

            # Engine should still be initialized
            assert starter.sql_engine is not None
        finally:
            _cleanup(tmpdir)

    def test_multiple_models_all_tables_created(self, tmp_path):
        """Multiple PySpringModel subclasses should all have their tables created."""
        db_path = str(tmp_path / "multi.db")
        db_uri = f"sqlite:///{db_path}"
        config_path, tmpdir = _create_app_fixture(db_uri)
        try:
            app = _run_app(config_path)
            starter = app.starters[0]

            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(starter.sql_engine)
            table_names = inspector.get_table_names()
            assert "e2e_item" in table_names
            assert "e2e_category" in table_names
        finally:
            _cleanup(tmpdir)

    def test_multiple_models_crud_across_repositories(self, tmp_path):
        """CRUD should work across multiple model types in the same app context."""
        db_path = str(tmp_path / "multi_crud.db")
        db_uri = f"sqlite:///{db_path}"
        config_path, tmpdir = _create_app_fixture(db_uri)
        try:
            _run_app(config_path)

            item_repo = ItemRepository()
            cat_repo = CategoryRepository()

            item_repo.save(Item(name="Bolt", quantity=100))
            cat_repo.save(Category(label="Hardware"))

            items = item_repo.find_all()
            categories = cat_repo.find_all()

            assert len(items) == 1
            assert items[0].name == "Bolt"
            assert len(categories) == 1
            assert categories[0].label == "Hardware"
        finally:
            _cleanup(tmpdir)

    def test_upsert_operations(self, tmp_path):
        """Upsert should insert when missing and update when present."""
        db_path = str(tmp_path / "upsert.db")
        db_uri = f"sqlite:///{db_path}"
        config_path, tmpdir = _create_app_fixture(db_uri)
        try:
            _run_app(config_path)
            repo = ItemRepository()

            # Insert via upsert (new entity)
            item = Item(name="Screw", quantity=50)
            repo.upsert(item, {"name": "Screw"})
            found = repo.find_all()
            assert len(found) == 1
            assert found[0].name == "Screw"
            assert found[0].quantity == 50

            # Update via upsert (fetch existing, modify, then upsert)
            existing = repo.find_by_id(found[0].id)
            assert existing is not None
            existing.quantity = 200
            repo.upsert(existing, {"id": existing.id})
            updated = repo.find_all()
            assert len(updated) == 1
            assert updated[0].quantity == 200
        finally:
            _cleanup(tmpdir)

    def test_delete_all_operations(self, tmp_path):
        """delete_all and delete_all_by_ids should work through the framework lifecycle."""
        db_path = str(tmp_path / "delete_all.db")
        db_uri = f"sqlite:///{db_path}"
        config_path, tmpdir = _create_app_fixture(db_uri)
        try:
            _run_app(config_path)
            repo = ItemRepository()

            repo.save(Item(name="A", quantity=1))
            repo.save(Item(name="B", quantity=2))
            repo.save(Item(name="C", quantity=3))
            assert len(repo.find_all()) == 3

            # delete_all_by_ids
            repo.delete_all_by_ids([1, 2])
            remaining = repo.find_all()
            assert len(remaining) == 1
            assert remaining[0].name == "C"

            # delete_all
            repo.delete_all(remaining)
            assert len(repo.find_all()) == 0
        finally:
            _cleanup(tmpdir)

    def test_save_all_bulk_insert(self, tmp_path):
        """save_all should bulk-insert multiple entities in one call."""
        db_path = str(tmp_path / "save_all.db")
        db_uri = f"sqlite:///{db_path}"
        config_path, tmpdir = _create_app_fixture(db_uri)
        try:
            _run_app(config_path)
            repo = ItemRepository()

            items = [
                Item(name="X", quantity=10),
                Item(name="Y", quantity=20),
                Item(name="Z", quantity=30),
            ]
            repo.save_all(items)

            found = repo.find_all()
            assert len(found) == 3
            names = {i.name for i in found}
            assert names == {"X", "Y", "Z"}
        finally:
            _cleanup(tmpdir)

    def test_missing_properties_raises_error(self, tmp_path):
        """When py_spring_model properties key is missing, the app should fail at startup."""
        from py_spring_core import PySpringApplication

        tmpdir = str(tmp_path / "bad_props")
        os.makedirs(tmpdir, exist_ok=True)
        src_dir = os.path.join(tmpdir, "src")
        os.makedirs(src_dir, exist_ok=True)
        with open(os.path.join(src_dir, "__init__.py"), "w") as f:
            f.write("")

        app_config = {
            "app_src_target_dir": src_dir,
            "server_config": {"host": "0.0.0.0", "port": 8080, "enabled": False},
            "properties_file_path": os.path.join(tmpdir, "application-properties.json"),
            "loguru_config": {"log_file_path": "", "log_level": "DEBUG"},
            "shutdown_config": {"timeout_seconds": 5.0, "enabled": False},
        }

        # Empty properties — no py_spring_model key
        config_path = os.path.join(tmpdir, "app-config.json")
        with open(config_path, "w") as f:
            json.dump(app_config, f)
        with open(app_config["properties_file_path"], "w") as f:
            json.dump({}, f)

        with pytest.raises(TypeError, match="py_spring_model is not found"):
            app = PySpringApplication(
                config_path,
                starters=[PySpringModelProvider()],
            )
            app.run()

        _cleanup(tmpdir)


# ---------------------------------------------------------------------------
# PostgreSQL E2E tests (testcontainers)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestPySpringModelProviderPostgres:
    """E2E tests using PostgreSQL via testcontainers."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from testcontainers.postgres import PostgresContainer

        self.pg = PostgresContainer("postgres:16-alpine")
        self.pg.start()
        db_uri = self.pg.get_connection_url()
        self.config_path, self.tmpdir = _create_app_fixture(db_uri)
        self.app = _run_app(self.config_path)
        yield
        _cleanup(self.tmpdir)
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
        assert "e2e_category" in table_names

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

    def test_upsert_postgres(self):
        """Upsert should work against PostgreSQL."""
        repo = ItemRepository()

        # Insert via upsert
        repo.upsert(Item(name="PGItem", quantity=7), {"name": "PGItem"})
        found = repo.find_all()
        assert len(found) == 1
        assert found[0].quantity == 7

        # Update via upsert (fetch existing, modify, then upsert)
        existing = repo.find_by_id(found[0].id)
        assert existing is not None
        existing.quantity = 99
        repo.upsert(existing, {"id": existing.id})
        updated = repo.find_all()
        assert len(updated) == 1
        assert updated[0].quantity == 99

    def test_save_all_postgres(self):
        """save_all bulk insert against PostgreSQL."""
        repo = ItemRepository()
        repo.save_all([
            Item(name="P1", quantity=1),
            Item(name="P2", quantity=2),
        ])
        found = repo.find_all()
        assert len(found) == 2
