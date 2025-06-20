from typing import Awaitable, Callable
from fastapi import Request, Response
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_core import RestController


async def session_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """
    Middleware to ensure that the database session is properly cleaned up after each HTTP request.

    This middleware works with context-based session management using ContextVar.
    It guarantees that each request has its own isolated database session context, and
    that any session stored in the context is properly closed after the request is handled.

    It does NOT create or commit any transactions by itself. It is meant to be used
    in combination with a decorator-based transaction manager (e.g., @Transactional)
    which controls when to commit or rollback.

    This middleware acts as a safety net:
    - Ensures that the ContextVar-based session is cleared after each request.
    - Prevents session leakage between requests in case of unexpected exceptions or unhandled paths.
    - Complements nested transaction logic by guaranteeing session cleanup at request boundaries.

    Use this middleware when:
    - You are using context-local session handling (via contextvars).
    - You want to ensure that long-lived or leaked sessions don't accumulate.
    """
    try:
        response = await call_next(request)
        return response
    finally:
        SessionContextHolder.clear_session()

class SessionController(RestController):
    def post_construct(self) -> None:
        self.app.middleware("http")(session_middleware)

    