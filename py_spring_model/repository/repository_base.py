from typing import Type, TypeVar

from py_spring import Component
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.engine.base import Connection
from sqlmodel import Session

from py_spring_model.core.model import PySpringModel

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
