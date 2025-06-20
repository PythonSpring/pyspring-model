from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Optional,
    Type,
    TypeVar,
    Union,
    get_args,
)
from uuid import UUID

from sqlalchemy import Select
from sqlmodel import Session, select
from sqlmodel.sql.expression import Select, SelectOfScalar

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, Transactional
from py_spring_model.repository.repository_base import RepositoryBase

T = TypeVar("T", bound=PySpringModel)
ID = TypeVar("ID", UUID, int)


class SessionNotFoundError(Exception): ...


FT = TypeVar("FT", bound=Callable[..., Any])


class CrudRepository(RepositoryBase, Generic[ID, T]):
    """
    A CRUD (Create, Read, Update, Delete) repository implementation that provides common database operations for a single SQLModel entity.

    This repository is useful when you only need basic CRUD operations on a single database table.
    For more complex scenarios involving multiple tables, you should consider using the Unit of Work pattern provided by SQLModel.

    The repository provides the following methods:
    - `find_by_id`: Retrieve a single entity by its ID.
    - `find_all_by_ids`: Retrieve a list of entities by their IDs.
    - `find_all`: Retrieve all entities.
    - `save`: Save a single entity.
    - `save_all`: Save a list of entities.
    - `delete`: Delete a single entity.
    - `delete_all`: Delete a list of entities.
    - `delete_by_id`: Delete an entity by its ID.
    - `delete_all_by_ids`: Delete a list of entities by their IDs.
    - `upsert`: Perform an upsert operation (insert or update) on a single entity based on a set of query parameters.

    The repository uses the SQLModel library for interacting with the database and automatically handles session management and transaction handling.
    """

    def __init__(self) -> None:
        super().__init__()
        self.id_type, self.model_class = self._get_model_id_type_with_class()

    @classmethod
    def _get_model_id_type_with_class(cls) -> tuple[Type[ID], Type[T]]:
        return get_args(tp=cls.__mro__[0].__orig_bases__[0])

    @Transactional
    def _find_by_statement(
        self,
        statement: Union[Select, SelectOfScalar],
    ) -> Optional[T]:
        session = SessionContextHolder.get_or_create_session()

        return session.exec(statement).first()

    @Transactional
    def _find_by_query(
        self,
        query_by: dict[str, Any],
    ) -> Optional[T]:
        session = SessionContextHolder.get_or_create_session()
        statement = select(self.model_class).filter_by(**query_by)
        return session.exec(statement).first()


    @Transactional
    def _find_all_by_query(
        self,
        query_by: dict[str, Any],
    ) -> tuple[Session, list[T]]:
        session = SessionContextHolder.get_or_create_session()
        statement = select(self.model_class).filter_by(**query_by)
        return session, list(session.exec(statement).fetchall())

    @Transactional
    def _find_all_by_statement(
        self,
        statement: Union[Select, SelectOfScalar],
    ) -> list[T]:
        session = SessionContextHolder.get_or_create_session()
        return list(session.exec(statement).fetchall())

    @Transactional
    def find_by_id(self, id: ID) -> Optional[T]:
        session = SessionContextHolder.get_or_create_session()
        statement = select(self.model_class).where(self.model_class.id == id)  # type: ignore
        optional_entity = session.exec(statement).first()
        if optional_entity is None:
            return

        return optional_entity
    
    @Transactional
    def find_all_by_ids(self, ids: list[ID]) -> list[T]:
        session = SessionContextHolder.get_or_create_session()
        statement = select(self.model_class).where(self.model_class.id.in_(ids))  # type: ignore
        return [entity for entity in session.exec(statement).all()]  # type: ignore

    @Transactional
    def find_all(self) -> list[T]:
        session = SessionContextHolder.get_or_create_session()
        statement = select(self.model_class)  # type: ignore
        return [entity for entity in session.exec(statement).all()]  # type: ignore

    @Transactional
    def save(self, entity: T) -> T:
        session = SessionContextHolder.get_or_create_session()
        session.add(entity)
        return entity

    @Transactional
    def save_all(
        self,
        entities: Iterable[T],
    ) -> bool:
        session = SessionContextHolder.get_or_create_session()
        session.add_all(entities)
        return True

    @Transactional
    def delete(self, entity: T) -> bool:
        session = SessionContextHolder.get_or_create_session()
        optional_intance = self._find_by_query(entity.model_dump())
        if optional_intance is None:
            return False
        session.delete(optional_intance)
        return True

    @Transactional
    def delete_all(self, entities: Iterable[T]) -> bool:
        session = SessionContextHolder.get_or_create_session()
        ids = [entity.id for entity in entities] # type: ignore
        
        statement = select(self.model_class).where(self.model_class.id.in_(ids))  # type: ignore
        deleted_entities = self._find_all_by_statement(statement)
        if deleted_entities is None:
            return False
        
        for entity in deleted_entities:
            session.delete(entity)

        return True


    @Transactional
    def delete_by_id(self, _id: ID) -> bool:
        session = SessionContextHolder.get_or_create_session()
        entity = self._find_by_query({"id": _id})
        if entity is None:
            return False
        session.delete(entity)
        return True

    @Transactional
    def delete_all_by_ids(self, ids: list[ID]) -> bool:
        session = SessionContextHolder.get_or_create_session()
        statement = select(self.model_class).where(self.model_class.id.in_(ids))  # type: ignore
        deleted_entities = self._find_all_by_statement(statement)
        if deleted_entities is None:
            return False
        for entity in deleted_entities:
            session.delete(entity)
        return True

    @Transactional
    def upsert(self, entity: T, query_by: dict[str, Any]) -> T:
        session = SessionContextHolder.get_or_create_session()
        statement = select(self.model_class).filter_by(**query_by)  # type: ignore
        existing_entity = self._find_by_statement(statement)
        if existing_entity is not None:
            # If the entity exists, update its attributes
            for key, value in entity.model_dump().items():
                setattr(existing_entity, key, value)
            session.add(existing_entity)
        else:
            # If the entity does not exist, insert it
            session.add(entity)
        return entity
