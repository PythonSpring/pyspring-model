from typing import Any, Callable

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class RequiresNewHandler:
    """Handler for Propagation.REQUIRES_NEW.

    Implementation details:
        - Always creates a brand-new session and pushes a new TransactionState onto the
          context stack, regardless of whether a transaction already exists.
        - If a transaction is already active, it is effectively suspended — the new state
          is pushed on top, so inner code sees only the new session. Once the function
          completes (or fails), the new state is popped and the outer transaction resumes.
        - On success the new session is committed; on exception it is rolled back.
          The session is always closed and the state popped in the finally block.

    Usage scenarios:
        - Audit logging or event recording that must persist even if the outer transaction
          rolls back.
        - Operations that must be isolated from the caller's transaction (e.g., sending
          notifications, writing to a separate system).

    Example:
        @Transactional(propagation=Propagation.REQUIRES_NEW)
        def write_audit_log(self, message: str) -> None:
            # This commit/rollback is independent of the caller's transaction.
            self.audit_repo.save(AuditEntry(message=message))
    """

    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
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
