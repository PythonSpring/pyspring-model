from typing import Any, Callable, Protocol


class PropagationHandler(Protocol):
    """Protocol defining the interface for transaction propagation handlers.

    Each handler implements a specific propagation strategy that determines how
    a transactional method interacts with an existing (or absent) transaction context.
    The TransactionManager dispatches to the appropriate handler based on the
    Propagation enum value, mirroring Spring's seven propagation semantics.
    """

    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any: ...
