import inspect
from typing import Iterable, Type, cast

import py_spring_core.core.utils as core_utils
from loguru import logger
from py_spring_core import Component, EntityProvider
from py_spring_core.core.application.context.application_context import (
    ApplicationContext,
)
from sqlalchemy import create_engine
from sqlalchemy.exc import InvalidRequestError as SqlAlehemyInvalidRequestError
from sqlmodel import SQLModel

from py_spring_model.core.commons import ApplicationFileGroups, PySpringModelProperties
from py_spring_model.core.model import PySpringModel
from py_spring_model.repository.repository_base import RepositoryBase
from py_spring_model.py_spring_model_rest import PySpringModelRestService
from py_spring_model.py_spring_model_rest.controller.py_spring_model_rest_controller import (
    PySpringModelRestController,
)
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.crud_repository_implementation_service import (
    CrudRepositoryImplementationService,
)


class ApplicationContextNotSetError(Exception): ...


class PySpringModelProvider(EntityProvider, Component):
    """
    The `PySpringModelProvider` class is responsible for initializing the PySpring model provider, which includes:
    - Grouping file paths into class files and model files
    - Dynamically importing model modules
    - Creating all SQLModel tables
    - Setting up the SQLAlchemy engine and connection
    - Registering PySpring model classes and metadata

    This class is a key component in the PySpring model infrastructure, handling the setup and initialization of the model-related functionality.
    """

    props: PySpringModelProperties

    def _group_file_paths(self, files: Iterable[str]) -> ApplicationFileGroups:
        class_files: set[str] = set()
        model_files: set[str] = set()

        for file in files:
            py_file_name = self._get_file_base_name(file)
            if py_file_name in self.props.model_file_postfix_patterns:
                model_files.add(file)
            if file not in model_files:
                class_files.add(file)
        return ApplicationFileGroups(class_files=class_files, model_files=model_files)

    def _import_model_modules(self) -> None:
        logger.info(
            f"[SQLMODEL TABLE MODEL IMPORT] Import all models: {self.app_file_groups.model_files}"
        )

        def import_func_wrapper() -> set[type[object]]:
            return core_utils.dynamically_import_modules(
                self.app_file_groups.model_files,
                is_ignore_error=False,
                target_subclasses=[PySpringModel, SQLModel],
            )

        try:
            self._model_classes = import_func_wrapper()
        except SqlAlehemyInvalidRequestError as error:
            logger.warning(
                f"[ERROR ADVISE] Encounter {error.__class__.__name__} when importing model classes."
            )
            logger.error(
                f"[SQLMODEL TABLE MODEL IMPORT FAILED] Failed to import model modules: {error}"
            )
        self._model_classes = self._get_pyspring_model_inheritors()

    def _is_from_model_file(self, cls: Type[object]) -> bool:
        try:
            source_file_name = inspect.getsourcefile(cls)
        except TypeError as error:
            logger.warning(
                f"[CHECK MODEL FILE] Failed to get source file name for class: {cls.__name__}, largely due to built-in classes.\n Actual error: {error}"
            )
            return False
        if source_file_name is None:
            return False
        py_file_name = self._get_file_base_name(source_file_name)  # e.g., models.py
        return py_file_name in self.props.model_file_postfix_patterns

    def _get_file_base_name(self, file_path: str) -> str:
        return file_path.split("/")[-1]

    def _get_pyspring_model_inheritors(self) -> set[Type[object]]:
        # use dict to store all models, use a session to check if all models are mapped
        class_name_with_class_map: dict[str, Type[object]] = {}
        for _cls in set(PySpringModel.__subclasses__()):
            if _cls.__name__ in class_name_with_class_map:
                continue
            if not self._is_from_model_file(_cls):
                logger.warning(
                    f"[SQLMODEL TABLE MODEL IMPORT] {_cls.__name__} is not from model file, skip it."
                )
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

        PySpringModel.set_engine(self.sql_engine)
        PySpringModel.set_models(
            cast(list[Type[PySpringModel]], list(self._model_classes))
        )
        PySpringModel.set_metadata(SQLModel.metadata)
        RepositoryBase.engine = self.sql_engine
        RepositoryBase.connection = self.sql_engine.connect()

    def provider_init(self) -> None:
        self.app_context: ApplicationContext
        logger.info(
            f"[PYSPRING MODEL PROVIDER INIT] Initialize PySpringModelProvider with app context: {self.app_context}"
        )
        if self.app_context is None:
            raise ApplicationContextNotSetError(
                "AppContext is not set by the framework"
            )

        self.app_file_groups = self._group_file_paths(self.app_context.all_file_paths)
        self.sql_engine = create_engine(
            url=self.props.sqlalchemy_database_uri, echo=True
        )
        if self.app_context is None:
            raise ApplicationContextNotSetError(
                "AppContext is not set by the framework"
            )
        self._import_model_modules()
        self._create_all_tables()


def provide_py_spring_model() -> EntityProvider:
    return PySpringModelProvider(
        rest_controller_classes=[PySpringModelRestController],
        component_classes=[
            PySpringModelProvider,
            PySpringModelRestService,
            CrudRepositoryImplementationService,
        ],  # injecting self for getting properties
        properties_classes=[PySpringModelProperties],
    )
