from typing import Any, Callable, Protocol


class PropagationHandler(Protocol):
    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any: ...
