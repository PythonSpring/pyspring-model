from typing import Any, Callable

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class RequiredHandler:
    """Handler for Propagation.REQUIRED (default propagation).

    Implementation details:
        - If an active transaction exists, joins it by incrementing the depth counter
          and executes the function within the same session. The transaction is NOT
          committed or rolled back here; that responsibility belongs to the outermost
          transaction owner.
        - If no active transaction exists, creates a new session and pushes a new
          TransactionState onto the context stack. On success the session is committed;
          on exception it is rolled back. The session is always closed and the state
          popped in the finally block.

    Usage scenarios:
        - Default choice for most service-layer methods that need transactional guarantees.
        - Suitable when nested calls should share the same transaction (e.g., a service
          method calling multiple repository operations that should commit or fail together).

    Example:
        @Transactional  # defaults to REQUIRED
        def create_order(self, order: Order) -> None:
            self.order_repo.save(order)        # joins the same transaction
            self.audit_repo.log("created")     # joins the same transaction
    """

    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if SessionContextHolder.has_active_transaction():
            state = SessionContextHolder.current_state()
            assert state is not None
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
