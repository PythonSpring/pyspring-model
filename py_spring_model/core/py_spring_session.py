from typing import Iterable

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
            self.refresh(instance)
