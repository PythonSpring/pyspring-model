import pytest
from sqlalchemy import create_engine
from sqlmodel import Field, SQLModel
from loguru import logger

from py_spring_model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.core.duplicate_import_handler import DuplicateImportHandler
from py_spring_model.core.registry_cleanup_handler import RegistryCleanupHandler
from py_spring_model.core.commons import PySpringModelProperties


class TestModelA(PySpringModel, table=True):
    """Test model A"""
    id: int = Field(default=None, primary_key=True)
    name: str


class TestModelB(PySpringModel, table=True):
    """Test model B"""
    id: int = Field(default=None, primary_key=True)
    description: str


class TestHandlers:
    """Test the new handler classes"""
    
    def setup_method(self):
        logger.info("Setting up test environment...")
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel._engine = self.engine
        SessionContextHolder.clear_session()
        
        # Create test properties
        self.props = PySpringModelProperties(
            model_file_postfix_patterns={"models.py", "test_handlers.py"},
            sqlalchemy_database_uri="sqlite:///:memory:"
        )

    def teardown_method(self):
        logger.info("Tearing down test environment...")
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear_session()

    def test_duplicate_import_handler(self):
        """Test that DuplicateImportHandler correctly identifies unique models"""
        handler = DuplicateImportHandler(self.props)
        unique_models = handler.get_unique_model_classes()
        
        # Should find our test models
        model_names = {model.__name__ for model in unique_models}
        assert "TestModelA" in model_names
        assert "TestModelB" in model_names
        
        # Should not have duplicates
        assert len(unique_models) == len(model_names)

    def test_registry_cleanup_handler(self):
        """Test that RegistryCleanupHandler can clean up registry conflicts"""
        handler = RegistryCleanupHandler()
        
        # This should not raise any errors
        handler.cleanup_registry_conflicts()
        
        # Verify that tables can still be created
        SQLModel.metadata.create_all(self.engine)
        
        # Check that our test tables were created
        from sqlalchemy import inspect
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        assert "testmodela" in tables
        assert "testmodelb" in tables

    def test_handlers_work_together(self):
        """Test that both handlers work together correctly"""
        # Use duplicate import handler to get unique models
        duplicate_handler = DuplicateImportHandler(self.props)
        unique_models = duplicate_handler.get_unique_model_classes()
        
        # Use registry cleanup handler to clean up any conflicts
        cleanup_handler = RegistryCleanupHandler()
        cleanup_handler.cleanup_registry_conflicts()
        
        # Should be able to create tables without errors
        SQLModel.metadata.create_all(self.engine)
        
        # Verify models were processed correctly
        assert len(unique_models) >= 2  # At least our two test models
        logger.success("Handlers work together correctly") 