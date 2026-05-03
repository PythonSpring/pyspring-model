from sqlalchemy import create_engine
from sqlmodel import Field, SQLModel

from py_spring_model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.py_spring_model_rest.service.py_spring_model_rest_service import (
    PySpringModelRestService,
)


class RestUser(PySpringModel, table=True):
    __tablename__ = "rest_user"
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str


class TestPySpringModelRestService:
    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([RestUser])
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)
        self.service = PySpringModelRestService()

    def teardown_method(self):
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear()

    def test_create_and_get(self):
        user = RestUser(name="Alice", email="alice@example.com")
        self.service.create(user)
        result = self.service.get(RestUser, user.id)
        assert result is not None
        assert result.name == "Alice"

    def test_get_not_found(self):
        result = self.service.get(RestUser, 999)
        assert result is None

    def test_update_returns_entity(self):
        user = RestUser(name="Alice", email="alice@example.com")
        self.service.create(user)
        updated = RestUser(name="Alice Updated", email="alice_new@example.com")
        result = self.service.update(user.id, updated)
        assert result is not None
        assert result.name == "Alice Updated"
        assert result.email == "alice_new@example.com"

    def test_update_not_found_returns_none(self):
        updated = RestUser(name="Nobody", email="nobody@example.com")
        result = self.service.update(999, updated)
        assert result is None

    def test_delete(self):
        user = RestUser(name="Alice", email="alice@example.com")
        self.service.create(user)
        self.service.delete(RestUser, user.id)
        result = self.service.get(RestUser, user.id)
        assert result is None

    def test_count(self):
        self.service.create(RestUser(name="A", email="a@e.com"))
        self.service.create(RestUser(name="B", email="b@e.com"))
        assert self.service.count(RestUser) == 2

    def test_count_empty(self):
        assert self.service.count(RestUser) == 0

    def test_batch_create(self):
        users = [
            RestUser(name="A", email="a@e.com"),
            RestUser(name="B", email="b@e.com"),
            RestUser(name="C", email="c@e.com"),
        ]
        result = self.service.batch_create(users)
        assert len(result) == 3
        assert self.service.count(RestUser) == 3

    def test_batch_delete(self):
        u1 = RestUser(name="A", email="a@e.com")
        u2 = RestUser(name="B", email="b@e.com")
        u3 = RestUser(name="C", email="c@e.com")
        self.service.create(u1)
        self.service.create(u2)
        self.service.create(u3)
        self.service.batch_delete(RestUser, [u1.id, u2.id])
        assert self.service.count(RestUser) == 1
        remaining = self.service.get(RestUser, u3.id)
        assert remaining is not None
        assert remaining.name == "C"
