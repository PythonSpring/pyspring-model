from typing import Any, Callable

from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class NotSupportedHandler:
    """Handler for Propagation.NOT_SUPPORTED.

    Implementation details:
        - If an active transaction exists, suspends it by pushing an empty TransactionState
          (session=None, depth=0) onto the context stack. This makes
          SessionContextHolder.has_active_transaction() return False for the duration of the
          function call. The empty state is popped in the finally block, restoring the
          original transaction context.
        - If no active transaction exists, simply executes the function directly with no
          additional state manipulation.

    Usage scenarios:
        - Operations that should never run inside a transaction, such as long-running
          computations, external API calls, or cache warming, where holding an open
          database transaction would be wasteful or harmful.
        - Ensuring that a method does not accidentally participate in the caller's
          transaction and cause unexpected lock contention.

    Example:
        @Transactional(propagation=Propagation.NOT_SUPPORTED)
        def send_email_notification(self, user: User) -> None:
            # Runs outside any transaction, even if the caller has one active.
            self.email_service.send(user.email, "Welcome!")
    """

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
