from typing import Any, Callable


class SupportsHandler:
    def handle(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
