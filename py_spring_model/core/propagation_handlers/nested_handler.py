from typing import Any, Callable

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class NestedHandler:
    """Handler for Propagation.NESTED.

    Implementation details:
        - If an active transaction exists, creates a SAVEPOINT within the current session
          via session.begin_nested(). On success the savepoint is committed (released);
          on exception the savepoint is rolled back, leaving the outer transaction intact
          so it can decide whether to continue or roll back entirely.
        - If no active transaction exists, behaves identically to REQUIRED: creates a new
          session, pushes a new TransactionState, and manages commit/rollback/close.

    Usage scenarios:
        - Partial failure tolerance within a larger transaction — e.g., processing a batch
          of items where individual item failures should be caught and logged without
          aborting the entire batch.
        - Implementing retry logic within a transaction: roll back to the savepoint and
          retry the nested operation without discarding the outer transaction's work.

    Note:
        SAVEPOINT support depends on the underlying database. Most relational databases
        (PostgreSQL, MySQL/InnoDB, SQLite with WAL) support this; some do not.

    Example:
        @Transactional
        def process_batch(self, items: list[Item]) -> None:
            for item in items:
                try:
                    self.process_single(item)  # NESTED — uses savepoint
                except Exception:
                    logger.warning(f"Skipping failed item {item.id}")

        @Transactional(propagation=Propagation.NESTED)
        def process_single(self, item: Item) -> None:
            # Savepoint rollback on failure; outer transaction continues.
            self.item_repo.save(item)
    """

    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if SessionContextHolder.has_active_transaction():
            state = SessionContextHolder.current_state()
            assert state is not None and state.session is not None
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
