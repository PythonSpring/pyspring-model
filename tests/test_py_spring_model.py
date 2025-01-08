

import pytest
from sqlalchemy import create_engine, MetaData
from sqlalchemy.engine.base import Connection
from sqlmodel import Field, SQLModel
from py_spring_model.core.py_spring_session import PySpringSession
from py_spring_model import PySpringModel


class SampleModel(PySpringModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str


class TestPySpringModel:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        self.metadata = MetaData()
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(self.metadata)
        yield
        PySpringModel._engine = None
        PySpringModel._metadata = None
        PySpringModel._connection = None

    def test_set_and_get_engine(self):
        assert PySpringModel.get_engine() == self.engine

    def test_set_and_get_metadata(self):
        assert PySpringModel.get_metadata() == self.metadata

    def test_set_and_get_connection(self):
        connection = PySpringModel.get_connection()
        assert isinstance(connection, Connection)
        assert not connection.closed

    def test_get_connection_reuse(self):
        connection1 = PySpringModel.get_connection()
        connection2 = PySpringModel.get_connection()
        assert connection1 is connection2

    def test_create_session(self):
        session = PySpringModel.create_session()
        assert isinstance(session, PySpringSession)
        assert session.bind == self.engine

    def test_create_managed_session_success(self):
        with PySpringModel.create_managed_session() as session:
            assert isinstance(session, PySpringSession)
            assert session.bind == self.engine

    def test_create_managed_session_exception(self):
        class TestException(Exception):
            pass

        with pytest.raises(TestException):
            with PySpringModel.create_managed_session() as session:
                assert isinstance(session, PySpringSession)
                raise TestException("Simulated error")

        with PySpringModel.create_managed_session() as session:
            # Ensure session is still functional after exception
            assert isinstance(session, PySpringSession)

    def test_set_models_and_get_model_lookup(self):
        PySpringModel.set_models([SampleModel])
        model_lookup = PySpringModel.get_model_lookup()
        assert model_lookup["samplemodel"] == SampleModel

    def test_get_primary_key_columns(self):
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([SampleModel])
        SampleModel.metadata.create_all(self.engine)
        primary_keys = PySpringModel.get_primary_key_columns(SampleModel)
        assert primary_keys == ["id"]

    def test_clone(self):
        sample = SampleModel(id=1, name="Test User")
        cloned_sample = sample.clone()
        assert cloned_sample.id == sample.id
        assert cloned_sample.name == sample.name
