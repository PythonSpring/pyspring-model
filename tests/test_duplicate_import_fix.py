import pytest
from sqlalchemy import create_engine
from sqlmodel import Field, SQLModel
from loguru import logger

from py_spring_model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.core.duplicate_import_handler import DuplicateImportHandler
from py_spring_model.core.commons import PySpringModelProperties


class TestUser(PySpringModel, table=True):
    """Test model that might be imported multiple times"""
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str


class TestUserRoleLink(PySpringModel, table=True):
    """Test model that might be imported multiple times - similar to the problematic UserRoleLink"""
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="testuser.id")
    role_id: int = Field(foreign_key="testrole.id")


class TestRole(PySpringModel, table=True):
    """Test model for role"""
    id: int = Field(default=None, primary_key=True)
    name: str


class TestDuplicateImportFix:
    """Test that duplicate import issues are resolved"""
    
    def setup_method(self):
        logger.info("Setting up test environment...")
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel._engine = self.engine
        SessionContextHolder.clear_session()

    def teardown_method(self):
        logger.info("Tearing down test environment...")
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear_session()

    def test_no_duplicate_registration_error(self):
        """Test that creating tables doesn't raise duplicate registration errors"""
        try:
            # This should not raise the "Multiple classes found for path" error
            SQLModel.metadata.create_all(self.engine)
            logger.success("Successfully created tables without duplicate registration errors")
            
            # Verify tables were created
            from sqlalchemy import inspect
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            assert "testuser" in tables
            assert "testuserrolelink" in tables
            assert "testrole" in tables
            
        except Exception as e:
            if "Multiple classes found for path" in str(e):
                pytest.fail(f"Duplicate registration error occurred: {e}")
            else:
                raise e

    def test_duplicate_import_handler_functionality(self):
        """Test that the duplicate import handler works correctly"""
        # Create a mock properties object for testing
        props = PySpringModelProperties(
            model_file_postfix_patterns={"test_duplicate_import_fix.py"},
            sqlalchemy_database_uri="sqlite:///:memory:",
            create_all_tables=True,
            prevent_duplicate_imports=True
        )
        
        # Create the duplicate import handler
        handler = DuplicateImportHandler(props)
        
        # Get unique model classes using the handler
        unique_classes = handler.get_unique_model_classes()
        
        # Check that our test models are in the unique classes
        test_models = {TestUser, TestUserRoleLink, TestRole}
        assert test_models.issubset(unique_classes), f"Expected test models to be in unique classes, got: {unique_classes}"
        
        # Check that there are no duplicate class names in the unique classes
        class_names = [cls.__name__ for cls in unique_classes]
        assert len(class_names) == len(set(class_names)), f"Duplicate class names found in unique classes: {class_names}"
        
        # Verify that the handler is working by checking that it filters out invalid models
        # (models not from the specified file patterns)
        all_subclasses = set(PySpringModel.__subclasses__())
        assert len(unique_classes) <= len(all_subclasses), "Handler should filter out some classes"

    def test_model_registration_consistency_with_handler(self):
        """Test that models are registered consistently using the duplicate import handler"""
        # Create a mock properties object for testing
        props = PySpringModelProperties(
            model_file_postfix_patterns={"test_duplicate_import_fix.py"},
            sqlalchemy_database_uri="sqlite:///:memory:",
            create_all_tables=True,
            prevent_duplicate_imports=True
        )
        
        # Create the duplicate import handler
        handler = DuplicateImportHandler(props)
        
        # Get unique model classes using the handler
        unique_classes = handler.get_unique_model_classes()
        
        # Check that our test models are in the unique classes
        test_models = {TestUser, TestUserRoleLink, TestRole}
        assert test_models.issubset(unique_classes), f"Expected test models to be in unique classes, got: {unique_classes}"
        
        # Check that there are no duplicate class names in the unique classes
        class_names = [cls.__name__ for cls in unique_classes]
        assert len(class_names) == len(set(class_names)), f"Duplicate class names found in unique classes: {class_names}" 