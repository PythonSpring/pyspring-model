from typing import Any, Callable

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class NestedHandler:
    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if SessionContextHolder.has_active_transaction():
            state = SessionContextHolder.current_state()
            nested_txn = state.session.begin_nested()
            try:
                result = func(*args, **kwargs)
                nested_txn.commit()
                return result
            except Exception:
                nested_txn.rollback()
                raise
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
