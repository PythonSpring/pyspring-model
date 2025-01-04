from typing import Iterable

from sqlmodel import Session, SQLModel


class PySpringSession(Session):
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
