from typing import Any, Callable

from py_spring_model.core.propagation import TransactionRequiredError
from py_spring_model.core.session_context_holder import SessionContextHolder


class MandatoryHandler:
    """Handler for Propagation.MANDATORY.

    Implementation details:
        - If no active transaction exists, raises TransactionRequiredError immediately.
          This handler never creates a new transaction.
        - If an active transaction exists, joins it by incrementing the depth counter
          and executes the function within the same session. The depth is decremented
          in the finally block. Commit/rollback is delegated to the outer transaction owner.

    Usage scenarios:
        - Methods that must always run within an existing transactional context and should
          fail fast if called without one.
        - Enforcing architectural constraints — e.g., ensuring a repository method is never
          called directly without a service-layer transaction wrapping it.

    Example:
        @Transactional(propagation=Propagation.MANDATORY)
        def debit_account(self, account_id: int, amount: Decimal) -> None:
            # Caller MUST already have a transaction; otherwise TransactionRequiredError is raised.
            account = self.account_repo.find(account_id)
            account.balance -= amount
    """

    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if not SessionContextHolder.has_active_transaction():
            raise TransactionRequiredError(
                "MANDATORY propagation requires an existing active transaction"
            )
        state = SessionContextHolder.current_state()
        assert state is not None
        state.depth += 1
        try:
            return func(*args, **kwargs)
        finally:
            state.depth -= 1
