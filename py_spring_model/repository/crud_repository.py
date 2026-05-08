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

from sqlalchemy import Select, func, inspect as sa_inspect
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
    def find_all(
        self,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        ascending: bool = True,
    ) -> list[T]:
        session = SessionContextHolder.get_or_create_session()
        statement = select(self.model_class)
        if order_by is not None:
            column = getattr(self.model_class, order_by)
            statement = statement.order_by(column.asc() if ascending else column.desc())
        if offset is not None:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        return list(session.exec(statement).all())

    def _is_new(self, entity: T) -> bool:
        state = sa_inspect(entity, raiseerr=False)
        if state is None:
            return True
        return state.transient

    @Transactional
    def save(self, entity: T) -> T:
        session = SessionContextHolder.get_or_create_session()
        if self._is_new(entity):
            session.add(entity)
            return entity
        return session.merge(entity)

    @Transactional
    def save_all(self, entities: Iterable[T]) -> list[T]:
        session = SessionContextHolder.get_or_create_session()
        result = []
        for entity in entities:
            if self._is_new(entity):
                session.add(entity)
                result.append(entity)
            else:
                result.append(session.merge(entity))
        return result

    @Transactional
    def save_and_flush(self, entity: T) -> T:
        session = SessionContextHolder.get_or_create_session()
        saved = self.save(entity)
        session.flush()
        return saved

    @Transactional
    def save_all_and_flush(self, entities: Iterable[T]) -> list[T]:
        session = SessionContextHolder.get_or_create_session()
        saved = self.save_all(entities)
        session.flush()
        return saved

    @Transactional
    def flush(self) -> None:
        session = SessionContextHolder.get_or_create_session()
        session.flush()

    @Transactional
    def delete(self, entity: T) -> None:
        session = SessionContextHolder.get_or_create_session()
        persisted = self._find_by_query({"id": entity.id})  # type: ignore
        if persisted is not None:
            session.delete(persisted)

    @Transactional
    def delete_all(self, entities: Iterable[T]) -> None:
        session = SessionContextHolder.get_or_create_session()
        ids = [entity.id for entity in entities]  # type: ignore
        if not ids:
            return
        statement = select(self.model_class).where(self.model_class.id.in_(ids))  # type: ignore
        for persisted in self._find_all_by_statement(statement):
            session.delete(persisted)

    @Transactional
    def delete_by_id(self, _id: ID) -> None:
        session = SessionContextHolder.get_or_create_session()
        entity = self._find_by_query({"id": _id})
        if entity is not None:
            session.delete(entity)

    @Transactional
    def delete_all_by_ids(self, ids: list[ID]) -> None:
        session = SessionContextHolder.get_or_create_session()
        statement = select(self.model_class).where(self.model_class.id.in_(ids))  # type: ignore
        for entity in self._find_all_by_statement(statement):
            session.delete(entity)

    @Transactional
    def count(self) -> int:
        session = SessionContextHolder.get_or_create_session()
        statement = select(func.count()).select_from(self.model_class)
        return session.exec(statement).one()

    @Transactional
    def count_by(self, query_by: dict[str, Any]) -> int:
        session = SessionContextHolder.get_or_create_session()
        statement = select(func.count()).select_from(self.model_class).filter_by(**query_by)
        return session.exec(statement).one()

    @Transactional
    def exists_by_id(self, id: ID) -> bool:
        session = SessionContextHolder.get_or_create_session()
        statement = select(func.count()).select_from(self.model_class).where(self.model_class.id == id)
        return session.exec(statement).one() > 0

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
