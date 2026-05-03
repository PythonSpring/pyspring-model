from typing import Any, Callable, ClassVar

from py_spring_model.core.propagation import Propagation
from py_spring_model.core.propagation_handlers.propagation_handler import PropagationHandler
from py_spring_model.core.propagation_handlers.required_handler import RequiredHandler
from py_spring_model.core.propagation_handlers.requires_new_handler import RequiresNewHandler
from py_spring_model.core.propagation_handlers.supports_handler import SupportsHandler
from py_spring_model.core.propagation_handlers.mandatory_handler import MandatoryHandler
from py_spring_model.core.propagation_handlers.not_supported_handler import NotSupportedHandler
from py_spring_model.core.propagation_handlers.never_handler import NeverHandler
from py_spring_model.core.propagation_handlers.nested_handler import NestedHandler


class TransactionManager:
    _handlers: ClassVar[dict[Propagation, PropagationHandler]] = {
        Propagation.REQUIRED: RequiredHandler(),
        Propagation.REQUIRES_NEW: RequiresNewHandler(),
        Propagation.SUPPORTS: SupportsHandler(),
        Propagation.MANDATORY: MandatoryHandler(),
        Propagation.NOT_SUPPORTED: NotSupportedHandler(),
        Propagation.NEVER: NeverHandler(),
        Propagation.NESTED: NestedHandler(),
    }

    @staticmethod
    def execute(func: Callable, propagation: Propagation, *args: Any, **kwargs: Any) -> Any:
        handler = TransactionManager._handlers[propagation]
        return handler.handle(func, *args, **kwargs)
