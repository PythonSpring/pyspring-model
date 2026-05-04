"""
Tests for RepositoryBase.
Covers: _execute_sql_returning_model(), _create_session(), create_managed_session().
"""

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlmodel import Field, SQLModel

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.py_spring_session import PySpringSession
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.repository.repository_base import RepositoryBase


class RepoItem(PySpringModel, table=True):
    __tablename__ = "repo_item"
    id: int = Field(default=None, primary_key=True)
    name: str
    price: float = 0.0


class RepoItemView(BaseModel):
    id: int
    name: str
    price: float


class TestRepositoryBase:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        SQLModel.metadata.create_all(self.engine)
        SessionContextHolder.clear()

        # Set up RepositoryBase class-level attributes
        RepositoryBase.engine = self.engine
        RepositoryBase.connection = self.engine.connect()

        self.repo = RepositoryBase.__new__(RepositoryBase)
        self.repo.engine = self.engine
        self.repo.connection = RepositoryBase.connection

        # Seed data
        with self.engine.connect() as conn:
            conn.execute(text("INSERT INTO repo_item (name, price) VALUES ('Widget', 9.99)"))
            conn.execute(text("INSERT INTO repo_item (name, price) VALUES ('Gadget', 19.99)"))
            conn.commit()

        yield
        SessionContextHolder.clear()
        try:
            RepositoryBase.connection.close()
        except Exception:
            pass
        RepositoryBase.engine = None
        RepositoryBase.connection = None
        SQLModel.metadata.drop_all(self.engine)
        PySpringModel._engine = None
        PySpringModel._metadata = None

    def test_execute_sql_returning_model_happy_path(self):
        """Should execute SQL and return a list of validated models."""
        results = self.repo._execute_sql_returning_model(
            "SELECT id, name, price FROM repo_item ORDER BY id",
            RepoItemView,
        )
        assert len(results) == 2
        assert isinstance(results[0], RepoItemView)
        assert results[0].name == "Widget"
        assert results[0].price == 9.99
        assert results[1].name == "Gadget"
        assert results[1].price == 19.99

    def test_execute_sql_returning_model_empty_result(self):
        """Should return an empty list when no rows match."""
        results = self.repo._execute_sql_returning_model(
            "SELECT id, name, price FROM repo_item WHERE name = 'NonExistent'",
            RepoItemView,
        )
        assert results == []

    def test_execute_sql_returning_model_single_result(self):
        """Should work with a single row result."""
        results = self.repo._execute_sql_returning_model(
            "SELECT id, name, price FROM repo_item WHERE name = 'Widget'",
            RepoItemView,
        )
        assert len(results) == 1
        assert results[0].name == "Widget"

    def test_create_session_returns_py_spring_session(self):
        """_create_session() should return a PySpringSession."""
        session = self.repo._create_session()
        assert isinstance(session, PySpringSession)
        session.close()

    def test_create_managed_session_returns_context_manager(self):
        """create_managed_session() should return a usable context manager."""
        with self.repo.create_managed_session() as session:
            assert isinstance(session, PySpringSession)
            result = session.execute(text("SELECT COUNT(*) FROM repo_item")).scalar()
            assert result == 2
