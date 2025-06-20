from contextvars import ContextVar
from enum import IntEnum
from functools import wraps
from typing import Any, Callable, ClassVar, Optional

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.py_spring_session import PySpringSession

class TransactionalDepth(IntEnum):
    OUTERMOST = 1
    ON_EXIT = 0

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

    Only outer_operation will commit or rollback.
    If create_user() or update_account() raises an exception,
    the whole transaction will be rolled back.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Increment session depth and get session
        session_depth = SessionContextHolder.enter_session()
        session = SessionContextHolder.get_or_create_session()
        try:
            result = func(*args, **kwargs)
            # Only commit at the outermost level (session_depth == 1)
            if session_depth == TransactionalDepth.OUTERMOST.value:
                session.commit()
            return result
        except Exception as error:
            # Only rollback at the outermost level (session_depth == 1)
            if session_depth == TransactionalDepth.OUTERMOST.value:
                session.rollback()
            raise error
        finally:
            # Decrement depth and clean up session if needed
            SessionContextHolder.exit_session()
    return wrapper

class SessionContextHolder:
    """
    A context holder for the session with explicit depth tracking.
    This is used to store the session in a context variable so that it can be accessed by the query service.
    The depth counter ensures that only the outermost transaction manages commit/rollback operations.
    """
    _session: ClassVar[ContextVar[Optional[PySpringSession]]] = ContextVar("session", default=None)
    _session_depth: ClassVar[ContextVar[int]] = ContextVar("session_depth", default=0)
    
    @classmethod
    def get_or_create_session(cls) -> PySpringSession:
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
    def get_session_depth(cls) -> int:
        """Get the current session depth."""
        return cls._session_depth.get()
    
    @classmethod
    def enter_session(cls) -> int:
        """
        Enter a new session context and increment the depth counter.
        Returns the new depth level.
        """
        current_depth = cls._session_depth.get()
        new_depth = current_depth + 1
        cls._session_depth.set(new_depth)
        return new_depth
    
    @classmethod
    def exit_session(cls) -> int:
        """
        Exit the current session context and decrement the depth counter.
        If depth reaches 0, clear the session.
        Returns the new depth level.
        """
        current_depth = cls._session_depth.get()
        new_depth = max(0, current_depth - 1)  # Prevent negative depth
        cls._session_depth.set(new_depth)
        
        # Clear session only when depth reaches 0 (outermost level)
        if new_depth == TransactionalDepth.ON_EXIT.value:
            cls.clear_session()
        
        return new_depth
    
    @classmethod
    def clear_session(cls):
        """Clear the session and reset depth to 0."""
        session = cls._session.get()
        if session is not None:
            session.close()
        cls._session.set(None)
        cls._session_depth.set(TransactionalDepth.ON_EXIT.value)

    @classmethod
    def is_transaction_managed(cls) -> bool:
        return cls._session_depth.get() > TransactionalDepth.OUTERMOST.value