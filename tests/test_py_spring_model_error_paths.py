"""
Tests for PySpringModel error and edge-case paths.
Covers: get_engine/get_metadata/get_model_lookup when not set,
get_primary_key_columns with nonexistent table,
get_connection when connection is closed.
"""

import pytest
from sqlalchemy import create_engine, MetaData
from sqlmodel import Field

from py_spring_model.core.model import PySpringModel


class ErrorPathModel(PySpringModel, table=True):
    __tablename__ = "error_path_model"
    id: int = Field(default=None, primary_key=True)
    name: str = ""


class TestPySpringModelErrorPaths:
    def setup_method(self):
        PySpringModel._engine = None
        PySpringModel._metadata = None
        PySpringModel._connection = None
        PySpringModel._models = None

    def teardown_method(self):
        PySpringModel._engine = None
        PySpringModel._metadata = None
        PySpringModel._connection = None
        PySpringModel._models = None

    def test_get_engine_raises_when_not_set(self):
        with pytest.raises(ValueError, match="ENGINE NOT SET"):
            PySpringModel.get_engine()

    def test_get_metadata_raises_when_not_set(self):
        with pytest.raises(ValueError, match="METADATA NOT SET"):
            PySpringModel.get_metadata()

    def test_get_model_lookup_raises_when_not_set(self):
        with pytest.raises(ValueError, match="MODEL_LOOKUP NOT SET"):
            PySpringModel.get_model_lookup()

    def test_get_connection_raises_when_engine_not_set(self):
        """get_connection should raise when engine is None and no existing connection."""
        with pytest.raises(ValueError, match="ENGINE NOT SET"):
            PySpringModel.get_connection()

    def test_get_primary_key_columns_raises_for_nonexistent_table(self):
        """Should raise ValueError when table is not found in metadata."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel.set_engine(engine)
        # Use an empty metadata — no tables registered
        PySpringModel.set_metadata(MetaData())

        with pytest.raises(ValueError, match="not found in metadata"):
            PySpringModel.get_primary_key_columns(ErrorPathModel)

    def test_get_connection_creates_new_when_closed(self):
        """When existing connection is closed, a new one should be created."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel.set_engine(engine)

        # Get a connection, then close it
        conn1 = PySpringModel.get_connection()
        conn1.close()
        assert conn1.closed

        # get_connection should create a new one
        conn2 = PySpringModel.get_connection()
        assert not conn2.closed
        assert conn2 is not conn1

    def test_get_connection_reuses_open_connection(self):
        """When existing connection is open, it should be reused."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel.set_engine(engine)

        conn1 = PySpringModel.get_connection()
        conn2 = PySpringModel.get_connection()
        assert conn1 is conn2
        assert not conn1.closed
        conn1.close()
