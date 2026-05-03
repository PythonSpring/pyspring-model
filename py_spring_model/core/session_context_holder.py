from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Callable, ClassVar, Optional, ParamSpec, TypeVar

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.py_spring_session import PySpringSession


@dataclass
class TransactionState:
    session: Optional[PySpringSession] = None
    depth: int = 0


P = ParamSpec("P")
RT = TypeVar("RT")


def Transactional(func: Callable[P, RT]) -> Callable[P, RT]:
    """
    Decorator for managing database transactions.

    Supports both bare usage (@Transactional) and parameterized usage
    (@Transactional(propagation=Propagation.REQUIRES_NEW)).

    When used bare, defaults to REQUIRED propagation: joins an existing
    transaction if one exists, or creates a new one if not.
    """
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> RT:
        # Inline REQUIRED logic — will be replaced by TransactionManager in Task 12
        current = SessionContextHolder.current_state()
        if current is not None and current.session is not None and current.depth >= 1:
            # Join existing transaction
            current.depth += 1
            try:
                return func(*args, **kwargs)
            finally:
                current.depth -= 1
        else:
            # Create new transaction
            session = PySpringModel.create_session()
            state = TransactionState(session=session, depth=1)
            SessionContextHolder.push_state(state)
            try:
                result = func(*args, **kwargs)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
                SessionContextHolder.pop_state()
    return wrapper


class SessionContextHolder:
    _session_stack: ClassVar[ContextVar[Optional[list[TransactionState]]]] = ContextVar(
        "session_stack", default=None
    )

    @classmethod
    def _get_stack(cls) -> list[TransactionState]:
        stack = cls._session_stack.get(None)
        if stack is None:
            stack = []
            cls._session_stack.set(stack)
        return stack

    @classmethod
    def push_state(cls, state: TransactionState) -> None:
        cls._get_stack().append(state)

    @classmethod
    def pop_state(cls) -> TransactionState:
        stack = cls._get_stack()
        return stack.pop()

    @classmethod
    def current_state(cls) -> Optional[TransactionState]:
        stack = cls._get_stack()
        if not stack:
            return None
        return stack[-1]

    @classmethod
    def has_active_transaction(cls) -> bool:
        state = cls.current_state()
        if state is None:
            return False
        return state.session is not None and state.depth >= 1

    @classmethod
    def get_or_create_session(cls) -> PySpringSession:
        state = cls.current_state()
        if state is not None and state.session is not None:
            return state.session
        session = PySpringModel.create_session()
        if state is not None:
            state.session = session
        return session

    @classmethod
    def has_session(cls) -> bool:
        state = cls.current_state()
        return state is not None and state.session is not None

    @classmethod
    def clear(cls) -> None:
        stack = cls._get_stack()
        for state in stack:
            if state.session is not None:
                state.session.close()
        stack.clear()

    @classmethod
    def clear_session(cls) -> None:
        """Backward-compatible alias for clear()."""
        cls.clear()
