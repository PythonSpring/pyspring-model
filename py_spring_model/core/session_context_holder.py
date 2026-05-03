from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Callable, ClassVar, Optional, ParamSpec, TypeVar, Union, overload

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.py_spring_session import PySpringSession

if TYPE_CHECKING:
    from py_spring_model.core.propagation import Propagation


@dataclass
class TransactionState:
    session: Optional[PySpringSession] = None
    depth: int = 0


P = ParamSpec("P")
RT = TypeVar("RT")


@overload
def Transactional(func: Callable[P, RT]) -> Callable[P, RT]: ...
@overload
def Transactional(*, propagation: Propagation) -> Callable[[Callable[P, RT]], Callable[P, RT]]: ...

def Transactional(
    func: Optional[Callable[P, RT]] = None,
    *,
    propagation: Optional[Propagation] = None,
) -> Union[Callable[P, RT], Callable[[Callable[P, RT]], Callable[P, RT]]]:
    """
    Decorator for managing database transactions with propagation support.

    Supports both bare and parameterized usage:
        @Transactional
        def create_user(): ...

        @Transactional(propagation=Propagation.REQUIRES_NEW)
        def write_audit(): ...
    """
    from py_spring_model.core.propagation import Propagation as PropEnum
    from py_spring_model.core.transaction_manager import TransactionManager

    resolved_propagation = propagation if propagation is not None else PropEnum.REQUIRED

    def decorator(fn: Callable[P, RT]) -> Callable[P, RT]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> RT:
            return TransactionManager.execute(fn, resolved_propagation, *args, **kwargs)
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


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
