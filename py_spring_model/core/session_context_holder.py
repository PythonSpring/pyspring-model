from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, ClassVar, Optional
from sqlmodel import Session

from py_spring_model.core.model import PySpringModel

def Transactional(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator for managing database transactions in a nested-safe manner.

    This decorator ensures that:
    - A new session is created only if there is no active session (i.e., outermost transaction).
    - The session is committed, rolled back, and closed only by the outermost function.
    - Nested transactional functions share the same session and do not interfere with the commit/rollback behavior.

    Behavior Summary:
    - If this function is the outermost @Transactional in the call stack:
        - A new session is created.
        - On success, the session is committed.
        - On failure, the session is rolled back.
        - The session is closed after execution.
    - If this function is called within an existing transaction:
        - The existing session is reused.
        - No commit, rollback, or close is performed (delegated to the outermost function).

    Example:
        @Transactional
        def outer_operation():
            create_user()
            update_account()

        @Transactional
        def create_user():
            db.session.add(User(...))  # Uses same session as outer_operation

        @Transactional
        def update_account():
            db.session.add(Account(...))  # Uses same session as outer_operation

        # Only outer_operation will commit or rollback.
        # If create_user() or update_account() raises an exception,
        # the whole transaction will be rolled back.

    This design is similar to Spring's @Transactional
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        is_outermost_transaction = not SessionContextHolder.has_session()
        session = SessionContextHolder.get_or_create_session()
        try:
            result = func(*args, **kwargs)
            if is_outermost_transaction:
                session.commit()
            return result
        except Exception as error:
            if is_outermost_transaction:
                session.rollback()
            raise error
        finally:
            if is_outermost_transaction:
                SessionContextHolder.clear_session()
    return wrapper

class SessionContextHolder:
    """
    A context holder for the session.
    This is used to store the session in a context variable so that it can be accessed by the query service.
    This is useful for the query service to be able to access the session without having to pass it in as an argument.
    This is also useful for the query service to be able to access the session without having to pass it in as an argument.
    """
    _session: ClassVar[ContextVar[Optional[Session]]] = ContextVar("session", default=None)
    @classmethod
    def get_or_create_session(cls) -> Session:
        optional_session = cls._session.get()
        if optional_session is None:
            session = PySpringModel.create_session()
            cls._session.set(session)
            return session
        return optional_session
    
    @classmethod
    def has_session(cls) -> bool:
        return cls._session.get() is not None
    
    @classmethod
    def clear_session(cls):
        session = cls._session.get()
        if session is not None:
            session.close()
        cls._session.set(None)