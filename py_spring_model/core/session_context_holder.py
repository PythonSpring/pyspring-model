from contextvars import ContextVar
from functools import wraps
from typing import ClassVar, Optional
from sqlmodel import Session

from py_spring_model.core.model import PySpringModel

def Transactional(func):
    """
    A decorator that wraps a function and commits the session if the function is successful.
    If the function raises an exception, the session is rolled back.
    The session is then closed.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        session = SessionContextHolder.get_or_create_session()
        try:
            result = func(*args, **kwargs)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
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
    def clear_session(cls):
        optional_session = cls._session.get()
        if optional_session is None:
            return
        optional_session.close()
        cls._session.set(None)