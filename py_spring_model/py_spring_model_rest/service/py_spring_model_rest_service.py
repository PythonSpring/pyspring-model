from typing import Optional, Type, TypeVar
from uuid import UUID

from py_spring_core import Component
from sqlalchemy import delete, func
from sqlmodel import select

from py_spring_model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, Transactional

ID = TypeVar("ID", int, UUID)
ModelT = TypeVar("ModelT", bound=PySpringModel)


class PySpringModelRestService(Component):
    """
    REST service for interacting with PySpringModel instances.
    Provides CRUD operations, counting, and batch operations.
    """

    def get_all_models(self) -> dict[str, type[PySpringModel]]:
        return PySpringModel.get_model_lookup()

    @Transactional
    def get(self, model_type: Type[ModelT], id: ID) -> Optional[ModelT]:
        session = SessionContextHolder.get_or_create_session()
        return session.get(model_type, id)  # type: ignore

    @Transactional
    def get_all_by_ids(self, model_type: Type[ModelT], ids: list[ID]) -> list[ModelT]:
        session = SessionContextHolder.get_or_create_session()
        statement = select(model_type).where(model_type.id.in_(ids))  # type: ignore
        return list(session.exec(statement).all())

    @Transactional
    def get_all(
        self, model_type: Type[ModelT], limit: int, offset: int
    ) -> list[ModelT]:
        session = SessionContextHolder.get_or_create_session()
        statement = select(model_type).offset(offset).limit(limit)
        return list(session.exec(statement).all())

    @Transactional
    def create(self, model: ModelT) -> ModelT:
        session = SessionContextHolder.get_or_create_session()
        session.add(model)
        return model

    @Transactional
    def update(self, id: ID, model: ModelT) -> Optional[ModelT]:
        session = SessionContextHolder.get_or_create_session()
        model_type = type(model)
        primary_keys = PySpringModel.get_primary_key_columns(model_type)
        optional_model = session.get(model_type, id)  # type: ignore
        if optional_model is None:
            return None

        for key, value in model.model_dump().items():
            if key in primary_keys:
                continue
            setattr(optional_model, key, value)
        session.add(optional_model)
        return optional_model

    @Transactional
    def delete(self, model_type: Type[ModelT], id: ID) -> None:
        session = SessionContextHolder.get_or_create_session()
        statement = delete(model_type).where(model_type.id == id)  # type: ignore
        session.execute(statement)

    @Transactional
    def count(self, model_type: Type[ModelT]) -> int:
        session = SessionContextHolder.get_or_create_session()
        statement = select(func.count()).select_from(model_type)
        return session.exec(statement).one()

    @Transactional
    def batch_create(self, models: list[ModelT]) -> list[ModelT]:
        session = SessionContextHolder.get_or_create_session()
        session.add_all(models)
        return models

    @Transactional
    def batch_delete(self, model_type: Type[ModelT], ids: list[ID]) -> None:
        session = SessionContextHolder.get_or_create_session()
        statement = delete(model_type).where(model_type.id.in_(ids))  # type: ignore
        session.execute(statement)
