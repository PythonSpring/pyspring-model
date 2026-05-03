from typing import Any, Callable

from py_spring_model.core.propagation import ExistingTransactionError
from py_spring_model.core.session_context_holder import SessionContextHolder


class NeverHandler:
    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if SessionContextHolder.has_active_transaction():
            raise ExistingTransactionError(
                "NEVER propagation does not allow an existing active transaction"
            )
        return func(*args, **kwargs)
