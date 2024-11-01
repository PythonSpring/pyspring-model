import contextlib
from typing import ClassVar, Iterator, Optional

from loguru import logger
from sqlalchemy import Engine, MetaData
from sqlalchemy.engine.base import Connection
from sqlmodel import Session, SQLModel

from py_spring_model.core.py_spring_session import PySpringSession


class PySpringModel(SQLModel):
    """
    Represents a PySpring model, which is a subclass of SQLModel.

    The `engine` class variable is an optional reference to an SQLAlchemy Engine instance,
    which can be used for database operations related to this model.
    """

    __table_args__ = {"extend_existing": True}
    _engine: ClassVar[Optional[Engine]] = None
    _models: ClassVar[Optional[list[type["PySpringModel"]]]] = None
    _metadata: ClassVar[Optional[MetaData]] = None
    _connection: ClassVar[Optional[Connection]] = None

    @classmethod
    def set_metadata(cls, metadata: MetaData) -> None:
        cls._metadata = metadata

    @classmethod
    def set_engine(cls, engine: Engine) -> None:
        cls._engine = engine

    @classmethod
    def set_models(cls, models: list[type["PySpringModel"]]) -> None:
        cls._models = models

    @classmethod
    def get_engine(cls) -> Engine:
        """
        Returns the SQLAlchemy Engine instance associated with this model.

        Returns:
            The SQLAlchemy Engine instance.
        """
        if cls._engine is None:
            raise ValueError("[ENGINE NOT SET] SQL Engine is not set")

        return cls._engine

    @classmethod
    def get_connection(cls) -> Connection:
        if cls._connection is not None and not cls._connection.closed:
            return cls._connection

        if cls._engine is None:
            raise ValueError("[ENGINE NOT SET] SQL Engine is not set")
        cls._connection = cls._engine.connect()
        return cls._connection

    @classmethod
    def get_metadata(cls) -> MetaData:
        if cls._metadata is None:
            raise ValueError("[METADATA NOT SET] SQL MetaData is not set")
        return cls._metadata

    @classmethod
    def get_model_lookup(cls) -> dict[str, type["PySpringModel"]]:
        if cls._models is None:
            raise ValueError("[MODEL_LOOKUP NOT SET] Model lookup is not set")
        return {str(_model.__tablename__): _model for _model in cls._models}

    @classmethod
    def create_session(cls) -> PySpringSession:
        engine = cls.get_engine()
        return PySpringSession(engine, expire_on_commit=False)

    @classmethod
    @contextlib.contextmanager
    def create_managed_session(cls) -> Iterator[PySpringSession]:
        """
        Creates a managed session context that will automatically close the session when the context is exited.
        ## Example Syntax:
            with PySpringModel.create_managed_session() as session:
                Do something with the session
                The session will be automatically closed when the context is exited
        """
        try:
            session = cls.create_session()
            yield session
            logger.info("[MANAGED SESSION COMMIT] Session committing...")
            session.commit()
            logger.info("[MANAGED SESSION COMMIT] Session committed, refreshing instances...")
            session.refresh_current_session_instances()
            logger.success("[MANAGED SESSION COMMIT] Session committed.")
        except Exception as error:
            logger.error(error)
            logger.error("[MANAGED SESSION ROLLBACK] Session rolling back...")
            session.rollback()
            raise
        finally:
            logger.info("[MANAGED SESSION CLOSE] Session closing...")
            session.close()
