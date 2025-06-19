from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, ClassVar, Optional
from sqlmodel import Session

from py_spring_model.core.model import PySpringModel

def Transactional(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    A decorator that wraps a function and commits the session if the function is successful.
    If the function raises an exception, the session is rolled back.
    The session is then closed.
    If the function is the outermost function, the session is committed.
    If the function is not the outermost function, the session is not committed.
    If the function is not the outermost function, the session is not rolled back.
    If the function is not the outermost function, the session is not closed.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        is_outermost = not SessionContextHolder.has_session()
        session = SessionContextHolder.get_or_create_session()
        try:
            result = func(*args, **kwargs)
            if is_outermost:
                session.commit()
            return result
        except Exception as error:
            if is_outermost:
                session.rollback()
            raise error
        finally:
            if is_outermost:
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