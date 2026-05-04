import logging
from typing import Type, cast

from loguru import logger
from py_spring_core import PySpringStarter
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from py_spring_model.core.commons import PySpringModelProperties
from py_spring_model.core.model import PySpringModel
from py_spring_model.py_spring_model_rest.controller.session_controller import SessionController
from py_spring_model.repository.repository_base import RepositoryBase
from py_spring_model.py_spring_model_rest import PySpringModelRestService
from py_spring_model.py_spring_model_rest.controller.py_spring_model_rest_controller import PySpringModelRestController
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.crud_repository_implementation_service import (
    CrudRepositoryImplementationService,
)


class PySpringModelStarter(PySpringStarter):
    """
    The `PySpringModelStarter` class is responsible for initializing the PySpring model provider, which includes:
    - Dynamically importing model modules
    - Creating all SQLModel tables
    - Setting up the SQLAlchemy engine and connection
    - Registering PySpring model classes and metadata
    """

    def on_configure(self) -> None:
        self.rest_controller_classes.append(SessionController)
        self.rest_controller_classes.append(PySpringModelRestController)
        self.component_classes.append(PySpringModelRestService)
        self.properties_classes.append(PySpringModelProperties)

    def on_initialized(self) -> None:
        if self.app_context is None:
            raise RuntimeError(
                "PySpringModelStarter.on_initialized() called before app_context was set."
            )
        props = self.app_context.get_properties(PySpringModelProperties)
        if props is None:
            raise RuntimeError(
                "PySpringModelProperties not found. Ensure the 'py_spring_model' key exists in application-properties.json."
            )

        logger.info(
            f"[PYSPRING MODEL PROVIDER INIT] Initialize PySpringModelStarter with app context: {self.app_context}"
        )
        self.sql_engine = create_engine(
            url=props.sqlalchemy_database_uri, echo=False
        )
        self._setup_sqlalchemy_loguru_intercept()
        self._init_pyspring_model()
        self._init_repository_query_implementation()

        if not props.create_all_tables:
            logger.info("[SQLMODEL TABLE CREATION] Skip creating all tables, set create_all_tables to True to enable.")
            return
        self._create_all_tables()

    def _get_pyspring_model_inheritors(self) -> set[Type[object]]:
        class_name_with_class_map: dict[str, Type[object]] = {}
        for _cls in set(PySpringModel.__subclasses__()):
            if _cls.__name__ in class_name_with_class_map:
                continue
            class_name_with_class_map[_cls.__name__] = _cls
        return set(class_name_with_class_map.values())

    def _create_all_tables(self) -> None:
        table_names = SQLModel.metadata.tables.keys()
        logger.success(
            f"[SQLMODEL TABLE CREATION] Create all SQLModel tables, engine url: {self.sql_engine.url}, tables: {', '.join(table_names)}"
        )
        SQLModel.metadata.create_all(self.sql_engine)
        logger.success(
            f"[SQLMODEL TABLE MODEL IMPORT] Get model classes from PySpringModel inheritors: {', '.join([_cls.__name__ for _cls in self._model_classes])}"
        )

    def _setup_sqlalchemy_loguru_intercept(self) -> None:
        """Route SQLAlchemy engine logs through loguru only, preventing duplicate log entries."""

        class _InterceptHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                level: str | int
                try:
                    level = logger.level(record.levelname).name
                except ValueError:
                    level = record.levelno
                logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())

        sa_logger = logging.getLogger("sqlalchemy.engine")
        sa_logger.handlers = [_InterceptHandler()]
        sa_logger.setLevel(logging.INFO)
        sa_logger.propagate = False

    def _init_repository_query_implementation(self) -> None:
        implementation_service = CrudRepositoryImplementationService()
        logger.info("[QUERY IMPLEMENTATION] Implement query for all CrudRepositories...")
        implementation_service.implement_query_for_all_crud_repository_inheritors()
        logger.success("[QUERY IMPLEMENTATION] All repository queries are implemented.")

    def _init_pyspring_model(self) -> None:
        self._model_classes = self._get_pyspring_model_inheritors()
        PySpringModel.set_engine(self.sql_engine)
        PySpringModel.set_models(
            cast(list[Type[PySpringModel]], list(self._model_classes))
        )
        PySpringModel.set_metadata(SQLModel.metadata)
        RepositoryBase.engine = self.sql_engine
        RepositoryBase.connection = self.sql_engine.connect()
