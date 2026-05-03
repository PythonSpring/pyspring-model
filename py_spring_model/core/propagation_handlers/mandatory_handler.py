from typing import Any, Callable

from py_spring_model.core.propagation import TransactionRequiredError
from py_spring_model.core.session_context_holder import SessionContextHolder


class MandatoryHandler:
    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if not SessionContextHolder.has_active_transaction():
            raise TransactionRequiredError(
                "MANDATORY propagation requires an existing active transaction"
            )
        state = SessionContextHolder.current_state()
        state.depth += 1
        try:
            return func(*args, **kwargs)
        finally:
            state.depth -= 1
