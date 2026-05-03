from typing import Any, Callable


class SupportsHandler:
    """Handler for Propagation.SUPPORTS.

    Implementation details:
        - Executes the function directly without any transaction management.
        - If an active transaction exists in the context, the function naturally
          participates in it (since the session is available via SessionContextHolder).
        - If no active transaction exists, the function runs non-transactionally.
        - This handler performs no session creation, commit, rollback, or stack manipulation.

    Usage scenarios:
        - Read-only operations that can optionally benefit from an existing transaction's
          session (e.g., consistent reads within a transactional scope) but do not require
          one.
        - Methods that should work both inside and outside a transactional context without
          forcing transaction creation.

    Example:
        @Transactional(propagation=Propagation.SUPPORTS)
        def find_user(self, user_id: int) -> Optional[User]:
            # Runs in the caller's transaction if one exists, otherwise non-transactional.
            return self.user_repo.find_by_id(user_id)
    """

    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
