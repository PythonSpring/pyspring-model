import pytest
from sqlalchemy import create_engine
from sqlmodel import Field, SQLModel
from loguru import logger

from py_spring_model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder


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

    def test_model_registration_consistency(self):
        """Test that models are registered consistently"""
        # Get all PySpringModel subclasses
        subclasses = set(PySpringModel.__subclasses__())
        
        # Check that our test models are in the subclasses
        test_models = {TestUser, TestUserRoleLink, TestRole}
        assert test_models.issubset(subclasses), f"Expected test models to be subclasses, got: {subclasses}"
        
        # Check that there are no duplicate class names
        class_names = [cls.__name__ for cls in subclasses]
        assert len(class_names) == len(set(class_names)), f"Duplicate class names found: {class_names}" 