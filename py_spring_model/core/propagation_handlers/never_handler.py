from typing import Any, Callable

from py_spring_model.core.propagation import ExistingTransactionError
from py_spring_model.core.session_context_holder import SessionContextHolder


class NeverHandler:
    """Handler for Propagation.NEVER.

    Implementation details:
        - If an active transaction exists, raises ExistingTransactionError immediately.
          This is a strict guard — the method refuses to execute if any transaction is
          in progress.
        - If no active transaction exists, executes the function directly with no
          transaction management. No session is created, and no state is pushed.

    Usage scenarios:
        - Methods that must guarantee they are never executed within a transactional
          context, typically because they perform operations incompatible with transactions
          (e.g., DDL statements, full-text index rebuilds).
        - Stricter alternative to NOT_SUPPORTED — instead of silently suspending the
          transaction, NEVER fails loudly to surface programming errors.

    Example:
        @Transactional(propagation=Propagation.NEVER)
        def rebuild_search_index(self) -> None:
            # Raises ExistingTransactionError if called inside a transaction.
            self.search_engine.full_reindex()
    """

    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if SessionContextHolder.has_active_transaction():
            raise ExistingTransactionError(
                "NEVER propagation does not allow an existing active transaction"
            )
        return func(*args, **kwargs)
