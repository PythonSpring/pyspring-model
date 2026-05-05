"""
Tests for session_middleware and SessionController.
Covers: middleware session cleanup, post_construct registration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Field, SQLModel

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState
from py_spring_model.py_spring_model_rest.controller.session_controller import (
    session_middleware,
    SessionController,
)


class BaseSessionMiddleware:
    """Tests for the session_middleware ASGI middleware."""

    @pytest.fixture(autouse=True)
    def setup(self):
        PySpringModel.set_engine(self.engine)
        SessionContextHolder.clear()
        yield
        SessionContextHolder.clear()
        PySpringModel._engine = None

    def test_middleware_clears_session_after_successful_request(self):
        """Session context should be cleared after a normal request."""
        app = FastAPI()

        @app.middleware("http")
        async def mw(request, call_next):
            return await session_middleware(request, call_next)

        @app.get("/test")
        def test_endpoint():
            # Simulate having an active session
            state = TransactionState(session=MagicMock(), depth=1)
            SessionContextHolder.push_state(state)
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        # After the request, session context should be cleared
        assert SessionContextHolder.current_state() is None

    def test_middleware_clears_session_after_exception(self):
        """Session context should be cleared even if the endpoint raises."""
        app = FastAPI()

        @app.middleware("http")
        async def mw(request, call_next):
            return await session_middleware(request, call_next)

        @app.get("/error")
        def error_endpoint():
            state = TransactionState(session=MagicMock(), depth=1)
            SessionContextHolder.push_state(state)
            raise RuntimeError("Endpoint error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/error")
        assert response.status_code == 500
        # Session should still be cleared
        assert SessionContextHolder.current_state() is None

    def test_middleware_returns_response(self):
        """Middleware should pass through the response from call_next."""
        app = FastAPI()

        @app.middleware("http")
        async def mw(request, call_next):
            return await session_middleware(request, call_next)

        @app.get("/hello")
        def hello():
            return {"message": "hello"}

        client = TestClient(app)
        response = client.get("/hello")
        assert response.status_code == 200
        assert response.json() == {"message": "hello"}

    def test_middleware_clears_even_with_no_session(self):
        """Middleware should not fail when there is no session to clear."""
        app = FastAPI()

        @app.middleware("http")
        async def mw(request, call_next):
            return await session_middleware(request, call_next)

        @app.get("/clean")
        def clean():
            return {"clean": True}

        client = TestClient(app)
        response = client.get("/clean")
        assert response.status_code == 200
        assert SessionContextHolder.current_state() is None


class BaseSessionControllerPostConstruct:
    """Tests for SessionController.post_construct()."""

    def test_post_construct_registers_middleware(self):
        """post_construct should register session_middleware on the app."""
        app = MagicMock()
        controller = SessionController.__new__(SessionController)
        controller.app = app
        controller.post_construct()
        app.middleware.assert_called_once_with("http")
