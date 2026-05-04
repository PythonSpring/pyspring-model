"""
Tests for PySpringModelRestController route handlers.
Covers: _parse_id with UUID, POST/PUT error handling, actual route invocations.
"""

from uuid import UUID, uuid4

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, SQLModel

from py_spring_model import PySpringModel
from py_spring_model.core.commons import PySpringModelProperties
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.py_spring_model_rest.service.py_spring_model_rest_service import (
    PySpringModelRestService,
)
from py_spring_model.py_spring_model_rest.controller.py_spring_model_rest_controller import (
    PySpringModelRestController,
)


class RCHandlerUser(PySpringModel, table=True):
    __tablename__ = "rc_handler_user"
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str


class TestParseId:
    """Tests for _parse_id() across id annotation types."""

    def test_parse_id_with_int_annotation(self):
        result = PySpringModelRestController._parse_id("42", RCHandlerUser)
        assert result == 42
        assert isinstance(result, int)

    def test_parse_id_with_uuid_annotation(self):
        class UUIDModel(PySpringModel):
            id: UUID

        test_uuid = uuid4()
        result = PySpringModelRestController._parse_id(str(test_uuid), UUIDModel)
        assert isinstance(result, UUID)
        assert result == test_uuid

    def test_parse_id_with_uuid_already_uuid(self):
        class UUIDModel(PySpringModel):
            id: UUID

        test_uuid = uuid4()
        result = PySpringModelRestController._parse_id(test_uuid, UUIDModel)  # type: ignore
        assert result is test_uuid

    def test_parse_id_with_string_annotation(self):
        class StringIdModel(PySpringModel):
            id: str

        result = PySpringModelRestController._parse_id("abc-123", StringIdModel)
        assert result == "abc-123"


class TestRestControllerRouteHandlers:
    """Tests that invoke route handlers through FastAPI TestClient."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([RCHandlerUser])
        SessionContextHolder.clear()
        RCHandlerUser.metadata.create_all(self.engine)

        self.controller = PySpringModelRestController.__new__(PySpringModelRestController)
        self.controller.rest_service = PySpringModelRestService()
        self.controller.router = APIRouter()
        self.controller.properties = PySpringModelProperties(
            sqlalchemy_database_uri="sqlite:///:memory:",
            create_crud_routes=True,
        )
        self.controller._register_basic_crud_routes("rc_handler_user", RCHandlerUser)

        app = FastAPI()
        app.include_router(self.controller.router)
        self.client = TestClient(app)
        yield
        RCHandlerUser.metadata.drop_all(self.engine)
        SessionContextHolder.clear()
        PySpringModel._engine = None
        PySpringModel._metadata = None

    def _create_user(self, name: str = "Alice", email: str = "a@e.com") -> dict:
        """Helper to create a user via the REST service directly (avoids routing issues)."""
        user = RCHandlerUser(name=name, email=email)
        self.controller.rest_service.create(user)
        return {"id": user.id, "name": user.name, "email": user.email}

    def test_post_create_success(self):
        response = self.client.post("/rc_handler_user", json={"name": "Alice", "email": "a@e.com"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Alice"

    def test_post_create_invalid_data_returns_400(self):
        response = self.client.post("/rc_handler_user", json={"invalid_field": "value"})
        assert response.status_code == 400

    def test_get_by_id(self):
        user = self._create_user()
        response = self.client.get(f"/rc_handler_user/{user['id']}")
        assert response.status_code == 200
        assert response.json()["name"] == "Alice"

    def test_get_by_id_not_found(self):
        response = self.client.get("/rc_handler_user/999")
        assert response.status_code == 200
        assert response.json() is None

    def test_get_all(self):
        self._create_user("Alice", "a@e.com")
        self._create_user("Bob", "b@e.com")
        response = self.client.get("/rc_handler_user/10/0")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_count(self):
        self._create_user()
        response = self.client.get("/rc_handler_user/count")
        assert response.status_code == 200
        assert response.json() == 1

    def test_post_get_all_by_ids(self):
        u1 = self._create_user("Alice", "a@e.com")
        u2 = self._create_user("Bob", "b@e.com")
        response = self.client.post("/rc_handler_user/ids", json={"ids": [u1["id"], u2["id"]]})
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_batch_create(self):
        response = self.client.post("/rc_handler_user/batch", json=[
            {"name": "Alice", "email": "a@e.com"},
            {"name": "Bob", "email": "b@e.com"},
        ])
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_put_update_success(self):
        user = self._create_user()
        response = self.client.put(
            f"/rc_handler_user/{user['id']}",
            json={"name": "Alice Updated", "email": "new@e.com"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Alice Updated"

    def test_put_update_invalid_data_returns_400(self):
        user = self._create_user()
        response = self.client.put(f"/rc_handler_user/{user['id']}", json={"bad_field": 123})
        assert response.status_code == 400

    def test_delete_by_id(self):
        user = self._create_user()
        response = self.client.delete(f"/rc_handler_user/{user['id']}")
        assert response.status_code == 204

    def test_batch_delete_route_conflict(self):
        """DELETE /batch conflicts with DELETE /{id} due to route registration order.
        The /{id} route is registered before /batch, so FastAPI matches 'batch' as an id,
        causing int('batch') to fail with a ValueError in _parse_id."""
        self._create_user("Alice", "a@e.com")
        self._create_user("Bob", "b@e.com")
        with pytest.raises(ValueError, match="invalid literal for int"):
            self.client.request("DELETE", "/rc_handler_user/batch", json={"ids": [1, 2]})
