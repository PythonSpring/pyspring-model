from typing import Type, cast

from loguru import logger
from py_spring_core import Component, EntityProvider, ApplicationContextRequired
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from py_spring_model.core.commons import PySpringModelProperties
from py_spring_model.core.model import PySpringModel
from py_spring_model.py_spring_model_rest.controller.session_controller import SessionController
from py_spring_model.repository.repository_base import RepositoryBase
from py_spring_model.py_spring_model_rest import PySpringModelRestService
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.crud_repository_implementation_service import (
    CrudRepositoryImplementationService,
)


class ApplicationContextNotSetError(Exception): ...


class PySpringModelProvider(EntityProvider, Component, ApplicationContextRequired):
    """
    The `PySpringModelProvider` class is responsible for initializing the PySpring model provider, which includes:
    - Grouping file paths into class files and model files
    - Dynamically importing model modules
    - Creating all SQLModel tables
    - Setting up the SQLAlchemy engine and connection
    - Registering PySpring model classes and metadata

    This class is a key component in the PySpring model infrastructure, handling the setup and initialization of the model-related functionality.
    """

    def _get_props(self) -> PySpringModelProperties:
        app_context =  self.get_application_context()
        assert app_context is not None
        props = app_context.get_properties(PySpringModelProperties)
        assert props is not None
        return props

    def _get_pyspring_model_inheritors(self) -> set[Type[object]]:
        # use dict to store all models, use a session to check if all models are mapped
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

        
    def _init_pyspring_model(self) -> None:
        self._model_classes = self._get_pyspring_model_inheritors()
        PySpringModel.set_engine(self.sql_engine)
        PySpringModel.set_models(
            cast(list[Type[PySpringModel]], list(self._model_classes))
        )
        PySpringModel.set_metadata(SQLModel.metadata)
        RepositoryBase.engine = self.sql_engine
        RepositoryBase.connection = self.sql_engine.connect()
        
    def provider_init(self) -> None:
        props = self._get_props()
        logger.info(
            f"[PYSPRING MODEL PROVIDER INIT] Initialize PySpringModelProvider with app context: {self.app_context}"
        )
        self.sql_engine = create_engine(
            url=props.sqlalchemy_database_uri, echo=True
        )
        self._init_pyspring_model()
        props = self._get_props()
        if not props.create_all_tables:
            logger.info("[SQLMODEL TABLE CREATION] Skip creating all tables, set create_all_tables to True to enable.")
            return
        self._create_all_tables()


def provide_py_spring_model() -> EntityProvider:
    return PySpringModelProvider(
        rest_controller_classes=[
            # PySpringModelRestController
            SessionController
        ],
        component_classes=[
            PySpringModelRestService,
            CrudRepositoryImplementationService,
        ],
        properties_classes=[
            PySpringModelProperties
        ],
    )
