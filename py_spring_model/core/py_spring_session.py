from typing import Iterable

from loguru import logger
from sqlalchemy import inspect as sa_inspect
from sqlmodel import Session, SQLModel


class PySpringSession(Session):
    """

    A custom SQLAlchemy Session class that tracks the current session instances and provides methods to manage them.

    The `PySpringSession` class inherits from the `Session` class and adds the following functionality:

    - Maintains a list of the current session instances in the `current_session_instance` attribute.
    - Overrides the `add()` and `add_all()` methods to also add the instances to the `current_session_instance` list.
    - Provides a `refresh_current_session_instances()` method to refresh all the instances in the `current_session_instance` list.

    This custom Session class is useful for managing the lifecycle of SQLModel instances within a session, especially when working with complex data models or when you need to keep track of the current session instances.
    """

    def __init__(self, *args, **kwargs):
        self.current_session_instance: list[SQLModel] = []

        super().__init__(*args, **kwargs)

    def add(self, instance: SQLModel, _warn: bool = True) -> None:
        self.current_session_instance.append(instance)
        return super().add(instance, _warn)

    def add_all(self, instances: Iterable[SQLModel]) -> None:
        self.current_session_instance.extend(instances)
        return super().add_all(instances)

    def refresh_current_session_instances(self) -> None:
        for instance in self.current_session_instance:
            state = sa_inspect(instance, raiseerr=False)
            if state is None or not state.persistent:
                continue
            try:
                self.refresh(instance)
            except Exception:
                logger.debug(
                    "Could not refresh instance '{}', skipping",
                    type(instance).__name__,
                )

    def commit(self) -> None:
        # Import here to avoid circular import
        from py_spring_model.core.session_context_holder import SessionContextHolder
        state = SessionContextHolder.current_state()
        if state is not None and state.depth > 1:
            logger.warning("Commiting a transaction that is currently being managed by the outermost transaction is strongly discouraged...")
            return
        super().commit()
        self.refresh_current_session_instances()