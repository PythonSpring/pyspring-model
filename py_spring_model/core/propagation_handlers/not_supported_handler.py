from typing import Any, Callable

from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class NotSupportedHandler:
    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if SessionContextHolder.has_active_transaction():
            empty_state = TransactionState(session=None, depth=0)
            SessionContextHolder.push_state(empty_state)
            try:
                return func(*args, **kwargs)
            finally:
                SessionContextHolder.pop_state()
        else:
            return func(*args, **kwargs)
