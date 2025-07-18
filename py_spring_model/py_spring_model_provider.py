from typing import Iterable, Type, cast

import py_spring_core.core.utils as core_utils
from loguru import logger
from py_spring_core import Component, EntityProvider, ApplicationContextRequired
from sqlalchemy import create_engine
from sqlalchemy.exc import InvalidRequestError as SqlAlehemyInvalidRequestError
from sqlmodel import SQLModel

from py_spring_model.core.commons import ApplicationFileGroups, PySpringModelProperties
from py_spring_model.core.model import PySpringModel
from py_spring_model.core.duplicate_import_handler import DuplicateImportHandler
from py_spring_model.core.registry_cleanup_handler import RegistryCleanupHandler
from py_spring_model.py_spring_model_rest.controller.session_controller import SessionController
from py_spring_model.repository.repository_base import RepositoryBase
from py_spring_model.py_spring_model_rest import PySpringModelRestService
from py_spring_model.py_spring_model_rest.controller.py_spring_model_rest_controller import (
    PySpringModelRestController,
)
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

    def _group_file_paths(self, files: Iterable[str]) -> ApplicationFileGroups:
        props = self._get_props()

        class_files: set[str] = set()
        model_files: set[str] = set()

        for file in files:
            py_file_name = self._get_file_base_name(file)
            if py_file_name in props.model_file_postfix_patterns:
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
            # First, try to import modules dynamically
            imported_classes = import_func_wrapper()
            logger.info(f"[SQLMODEL TABLE MODEL IMPORT] Successfully imported {len(imported_classes)} classes dynamically")
        except SqlAlehemyInvalidRequestError as error:
            logger.warning(
                f"[ERROR ADVISE] Encounter {error.__class__.__name__} when importing model classes."
            )
            logger.error(
                f"[SQLMODEL TABLE MODEL IMPORT FAILED] Failed to import model modules: {error}"
            )
            # If dynamic import fails, fall back to getting subclasses
            logger.info("[SQLMODEL TABLE MODEL IMPORT] Falling back to subclass discovery method")
            imported_classes = set()
        
        # Get all PySpringModel subclasses and deduplicate by class name and module
        self._model_classes = self._get_pyspring_model_inheritors()
        
        # Log the final model classes for debugging
        logger.info(
            f"[SQLMODEL TABLE MODEL IMPORT] Final model classes: {', '.join([f'{_cls.__name__} ({_cls.__module__})' for _cls in self._model_classes])}"
        )

    def _get_file_base_name(self, file_path: str) -> str:
        """Extract the base file name from a file path."""
        return file_path.split("/")[-1]

    def _get_pyspring_model_inheritors(self) -> set[Type[PySpringModel]]:
        """
        Get unique PySpringModel classes using the duplicate import handler.
        """
        props = self._get_props()
        handler = DuplicateImportHandler(props)
        return handler.get_unique_model_classes()

    def _clear_sqlalchemy_registry_conflicts(self) -> None:
        """
        Clear any duplicate class registrations in SQLAlchemy's registry.
        This helps prevent the 'Multiple classes found for path' error.
        """
        handler = RegistryCleanupHandler()
        handler.cleanup_registry_conflicts()

    def _force_clear_sqlalchemy_registry_conflicts(self) -> None:
        """
        Force clear all registry conflicts using aggressive cleanup methods.
        This should be used when standard cleanup fails.
        """
        handler = RegistryCleanupHandler()
        handler.force_cleanup_all_registries()

    def _create_all_tables(self) -> None:
        props = self._get_props()
        
        # Clear any registry conflicts before creating tables if enabled
        if props.prevent_duplicate_imports:
            self._clear_sqlalchemy_registry_conflicts()

        table_names = SQLModel.metadata.tables.keys()
        logger.success(
            f"[SQLMODEL TABLE CREATION] Create all SQLModel tables, engine url: {self.sql_engine.url}, tables: {', '.join(table_names)}"
        )
        

        PySpringModel.set_engine(self.sql_engine)
        PySpringModel.set_models(
            cast(list[Type[PySpringModel]], list(self._model_classes))
        )
        PySpringModel.set_metadata(SQLModel.metadata)
        RepositoryBase.engine = self.sql_engine
        RepositoryBase.connection = self.sql_engine.connect()
        if not props.create_all_tables:
            logger.info("[SQLMODEL TABLE CREATION] Skip creating all tables, set create_all_tables to True to enable.")
            return
        
        try:
            SQLModel.metadata.create_all(self.sql_engine)
            logger.success(
                f"[SQLMODEL TABLE MODEL IMPORT] Get model classes from PySpringModel inheritors: {', '.join([_cls.__name__ for _cls in self._model_classes])}"
            )
        except SqlAlehemyInvalidRequestError as error:
            if "Multiple classes found for path" in str(error):
                logger.error(f"[TABLE CREATION ERROR] Duplicate class registration detected: {error}")
                if props.prevent_duplicate_imports:
                    logger.info("[TABLE CREATION ERROR] Attempting to resolve by clearing registry and retrying...")
                    
                    # Try standard cleanup first
                    self._clear_sqlalchemy_registry_conflicts()
                    try:
                        SQLModel.metadata.create_all(self.sql_engine)
                        logger.success("[TABLE CREATION] Successfully created tables after registry cleanup")
                    except SqlAlehemyInvalidRequestError as retry_error:
                        if "Multiple classes found for path" in str(retry_error):
                            logger.warning("[TABLE CREATION ERROR] Standard cleanup failed, trying forced cleanup...")
                            # Try forced cleanup
                            self._force_clear_sqlalchemy_registry_conflicts()
                            SQLModel.metadata.create_all(self.sql_engine)
                            logger.success("[TABLE CREATION] Successfully created tables after forced registry cleanup")
                        else:
                            raise retry_error
                else:
                    logger.error("[TABLE CREATION ERROR] Duplicate imports detected but prevent_duplicate_imports is disabled. Please enable it or fix the duplicate imports manually.")
                    raise error
            else:
                raise error

    def provider_init(self) -> None:
        props = self._get_props()
        logger.info(
            f"[PYSPRING MODEL PROVIDER INIT] Initialize PySpringModelProvider with app context: {self.app_context}"
        )
        app_context = self.get_application_context()

        self.app_file_groups = self._group_file_paths(app_context.all_file_paths)
        self.sql_engine = create_engine(
            url=props.sqlalchemy_database_uri, echo=True
        )
        self._import_model_modules()
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
