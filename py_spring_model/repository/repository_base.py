from contextlib import _GeneratorContextManager
from typing import Type, TypeVar

from py_spring_core import Component
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.engine.base import Connection
from sqlmodel import Session

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.py_spring_session import PySpringSession

T = TypeVar("T", bound=BaseModel)


class RepositoryBase(Component):
    engine: Engine
    connection: Connection

    def _execute_sql_returning_model(self, sql: str, model_cls: Type[T]) -> list[T]:
        cursor = self.connection.execute(text(sql))
        dict_results = [row._asdict() for row in cursor.fetchall()]
        results = [model_cls.model_validate(dict(row)) for row in dict_results]
        cursor.close()
        return results

    def _create_session(self) -> Session:
        return PySpringModel.create_session()

    def create_managed_session(self) -> _GeneratorContextManager[PySpringSession]:
        return PySpringModel.create_managed_session()
