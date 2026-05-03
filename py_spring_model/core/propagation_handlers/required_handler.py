from typing import Any, Callable

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class RequiredHandler:
    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if SessionContextHolder.has_active_transaction():
            state = SessionContextHolder.current_state()
            state.depth += 1
            try:
                return func(*args, **kwargs)
            finally:
                state.depth -= 1
        else:
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
