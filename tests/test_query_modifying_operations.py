import pytest
from loguru import logger
from sqlalchemy import create_engine, text
from sqlmodel import Field, SQLModel
from typing import Optional, List
from unittest.mock import patch, MagicMock

from py_spring_model import PySpringModel
from py_spring_model.py_spring_model_rest.service.query_service.query import Query, QueryExecutionService
from py_spring_model.repository.crud_repository import CrudRepository


class TestUser(PySpringModel, table=True):
    """Test model for INSERT/UPDATE operations"""
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int = Field(default=0)


class TestUserRepository(CrudRepository[int, TestUser]):
    """Test repository with Query decorators for modifying operations"""
    
    @Query("INSERT INTO testuser (name, email, age) VALUES ({name}, {email}, {age}) RETURNING *", is_modifying=True)
    def insert_user_with_commit(self, name: str, email: str, age: int) -> TestUser: 
        """INSERT operation that should commit changes"""
        ...

    
    @Query("INSERT INTO testuser (name, email, age) VALUES ({name}, {email}, {age})", is_modifying=False)
    def insert_user_without_commit(self, name: str, email: str, age: int) -> TestUser:
        """INSERT operation that should NOT commit changes"""
        ...
    
    @Query("UPDATE testuser SET name = {name}, age = {age} WHERE email = {email}", is_modifying=True)
    def update_user_with_commit(self, name: str, email: str, age: int) -> TestUser:
        """UPDATE operation that should commit changes"""
        ...
    
    @Query("UPDATE testuser SET name = {name}, age = {age} WHERE email = {email}", is_modifying=False)
    def update_user_without_commit(self, name: str, email: str, age: int) -> TestUser:
        """UPDATE operation that should NOT commit changes"""
        ...
    
    @Query("SELECT * FROM testuser WHERE email = {email}")
    def find_by_email(self, email: str) -> Optional[TestUser]:
        """SELECT operation for verification (readonly, no commit needed)"""
        ...
    
    @Query("SELECT * FROM testuser")
    def find_all_users(self) -> List[TestUser]:
        """SELECT operation to get all users"""
        ...


class TestQueryModifyingOperations:
    """Test suite for INSERT/UPDATE operations with is_modifying parameter"""
    
    def setup_method(self):
        """Set up test environment with in-memory SQLite database"""
        logger.info("Setting up test environment...")
        self.engine = create_engine("sqlite:///:memory:", echo=True)
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([TestUser])
        SQLModel.metadata.create_all(self.engine)
        self.repository = TestUserRepository()
        self.repository.insert_user_with_commit(name="John Doe", email="john@example.com", age=30)

    def teardown_method(self):
        """Clean up test environment"""
        logger.info("Tearing down test environment...")
        SQLModel.metadata.drop_all(self.engine)
    
    def test_insert_with_commit_true(self):
        """Test INSERT operation with is_modifying=True (should commit)"""
        # Mock the session to verify commit is called
        with patch.object(PySpringModel, 'create_managed_session') as mock_context:
            mock_session = MagicMock()
            mock_context.return_value.__enter__.return_value = mock_session
            mock_context.return_value.__exit__.return_value = None
            
            # Mock the execute result for INSERT
            mock_result = MagicMock()
            mock_result._asdict.return_value = {
                'id': 1, 'name': 'John Doe', 'email': 'john@example.com', 'age': 30
            }
            mock_session.execute.return_value.first.return_value = mock_result
            
            # Execute INSERT with is_modifying=True
            try:
                result = self.repository.insert_user_with_commit(
                    name="John Doe", 
                    email="john@example.com", 
                    age=30
                )
            except Exception:
                # Expected due to mocking, but we can verify the session call
                pass
            
            # Verify create_managed_session was called with should_commit=True
            mock_context.assert_called_once_with(should_commit=True)
    
    def test_insert_with_commit_false(self):
        """Test INSERT operation with is_modifying=False (should not commit)"""
        # Mock the session to verify commit is not called
        with patch.object(PySpringModel, 'create_managed_session') as mock_context:
            mock_session = MagicMock()
            mock_context.return_value.__enter__.return_value = mock_session
            mock_context.return_value.__exit__.return_value = None
            
            # Mock the execute result for INSERT
            mock_result = MagicMock()
            mock_result._asdict.return_value = {
                'id': 1, 'name': 'Jane Doe', 'email': 'jane@example.com', 'age': 25
            }
            mock_session.execute.return_value.first.return_value = mock_result
            
            # Execute INSERT with is_modifying=False
            try:
                result = self.repository.insert_user_without_commit(
                    name="Jane Doe", 
                    email="jane@example.com", 
                    age=25
                )
            except Exception:
                # Expected due to mocking, but we can verify the session call
                pass
            
            # Verify create_managed_session was called with should_commit=False
            mock_context.assert_called_once_with(should_commit=False)
    
    def test_update_with_commit_true(self):
        """Test UPDATE operation with is_modifying=True (should commit)"""
        # Mock the session to verify commit is called
        with patch.object(PySpringModel, 'create_managed_session') as mock_context:
            mock_session = MagicMock()
            mock_context.return_value.__enter__.return_value = mock_session
            mock_context.return_value.__exit__.return_value = None
            
            # Mock the execute result for UPDATE
            mock_result = MagicMock()
            mock_result._asdict.return_value = {
                'id': 1, 'name': 'John Updated', 'email': 'john@example.com', 'age': 35
            }
            mock_session.execute.return_value.first.return_value = mock_result
            
            # Execute UPDATE with is_modifying=True
            try:
                result = self.repository.update_user_with_commit(
                    name="John Updated", 
                    email="john@example.com", 
                    age=35
                )
            except Exception:
                # Expected due to mocking, but we can verify the session call
                pass
            
            # Verify create_managed_session was called with should_commit=True
            mock_context.assert_called_once_with(should_commit=True)
    
    def test_update_with_commit_false(self):
        """Test UPDATE operation with is_modifying=False (should not commit)"""
        # Mock the session to verify commit is not called
        with patch.object(PySpringModel, 'create_managed_session') as mock_context:
            mock_session = MagicMock()
            mock_context.return_value.__enter__.return_value = mock_session
            mock_context.return_value.__exit__.return_value = None
            
            # Mock the execute result for UPDATE
            mock_result = MagicMock()
            mock_result._asdict.return_value = {
                'id': 1, 'name': 'Jane Updated', 'email': 'jane@example.com', 'age': 30
            }
            mock_session.execute.return_value.first.return_value = mock_result
            
            # Execute UPDATE with is_modifying=False
            try:
                result = self.repository.update_user_without_commit(
                    name="Jane Updated", 
                    email="jane@example.com", 
                    age=30
                )
            except Exception:
                # Expected due to mocking, but we can verify the session call
                pass
            
            # Verify create_managed_session was called with should_commit=False
            mock_context.assert_called_once_with(should_commit=False)
    
    def test_query_execution_service_with_modifying_true(self):
        """Test QueryExecutionService.execute_query with is_modifying=True"""
        def dummy_insert_func(name: str, email: str, age: int) -> TestUser:
            return TestUser(name=name, email=email, age=age)
        
        # Mock the session behavior
        with patch.object(PySpringModel, 'create_managed_session') as mock_context:
            mock_session = MagicMock()
            mock_context.return_value.__enter__.return_value = mock_session
            mock_context.return_value.__exit__.return_value = None
            
            # Mock the execute result
            mock_result = MagicMock()
            mock_result._asdict.return_value = {
                'id': 1, 'name': 'Test User', 'email': 'test@example.com', 'age': 25
            }
            mock_session.execute.return_value.first.return_value = mock_result
            
            # Execute query with is_modifying=True
            try:
                QueryExecutionService.execute_query(
                    query_template="INSERT INTO testuser (name, email, age) VALUES ({name}, {email}, {age})",
                    func=dummy_insert_func,
                    kwargs={"name": "Test User", "email": "test@example.com", "age": 25},
                    is_modifying=True
                )
            except Exception:
                # Expected due to mocking
                pass
            
            # Verify create_managed_session was called with should_commit=True
            mock_context.assert_called_once_with(should_commit=True)
    
    def test_query_execution_service_with_modifying_false(self):
        """Test QueryExecutionService.execute_query with is_modifying=False"""
        def dummy_update_func(name: str, email: str, age: int) -> TestUser:
            return TestUser(name=name, email=email, age=age)
        
        # Mock the session behavior
        with patch.object(PySpringModel, 'create_managed_session') as mock_context:
            mock_session = MagicMock()
            mock_context.return_value.__enter__.return_value = mock_session
            mock_context.return_value.__exit__.return_value = None
            
            # Mock the execute result
            mock_result = MagicMock()
            mock_result._asdict.return_value = {
                'id': 1, 'name': 'Test User Updated', 'email': 'test@example.com', 'age': 30
            }
            mock_session.execute.return_value.first.return_value = mock_result
            
            # Execute query with is_modifying=False
            try:
                QueryExecutionService.execute_query(
                    query_template="UPDATE testuser SET name = {name}, age = {age} WHERE email = {email}",
                    func=dummy_update_func,
                    kwargs={"name": "Test User Updated", "email": "test@example.com", "age": 30},
                    is_modifying=False
                )
            except Exception:
                # Expected due to mocking
                pass
            
            # Verify create_managed_session was called with should_commit=False
            mock_context.assert_called_once_with(should_commit=False)
    
    def test_query_decorator_default_is_modifying_false(self):
        """Test that Query decorator defaults is_modifying to False"""
        @Query("SELECT * FROM testuser WHERE id = {id}")
        def select_user_by_id(id: int) -> Optional[TestUser]: ...
        
        # Mock the session behavior
        with patch.object(PySpringModel, 'create_managed_session') as mock_context:
            mock_session = MagicMock()
            mock_context.return_value.__enter__.return_value = mock_session
            mock_context.return_value.__exit__.return_value = None
            
            # Mock the execute result
            mock_result = MagicMock()
            mock_result._asdict.return_value = {
                'id': 1, 'name': 'Test User', 'email': 'test@example.com', 'age': 25
            }
            mock_session.execute.return_value.first.return_value = mock_result
            
            # Execute query without specifying is_modifying (should default to False)
            try:
                select_user_by_id(id=1)
            except Exception:
                # Expected due to mocking
                pass
            
            # Verify create_managed_session was called with should_commit=False (default)
            mock_context.assert_called_once_with(should_commit=False)
    
    def test_real_database_insert_with_commit(self):
        """Integration test: Real INSERT operation with commit"""
        # Create a user using direct repository save (which commits)
        initial_user = TestUser(name="Initial User", email="initial@example.com", age=20)
        saved_user = self.repository.save(initial_user)
        
        # Verify the user was saved
        assert saved_user.id is not None
        
        # Verify we can find the user
        users = self.repository.find_all()
        assert len(users) == 2  # John Doe from setup + Initial User from this test
        
        # Find the Initial User specifically
        initial_user_found = next((u for u in users if u.name == "Initial User"), None)
        assert initial_user_found is not None
        assert initial_user_found.name == "Initial User"
        assert initial_user_found.email == "initial@example.com"
        assert initial_user_found.age == 20
    
    def test_real_database_operations_persistence(self):
        """Integration test: Verify that committed operations persist"""
        # Insert a user using the repository's save method (which commits)
        user = TestUser(name="Persistent User", email="persistent@example.com", age=25)
        self.repository.save(user)
        
        # Verify the user exists by querying in a new session context
        with PySpringModel.create_managed_session() as session:
            result = session.execute(text("SELECT * FROM testuser WHERE email = 'persistent@example.com'")).first()
            assert result is not None
            assert result.name == "Persistent User"
            assert result.age == 25
    
    def test_session_commit_parameter_propagation(self):
        """Test that the should_commit parameter is properly propagated"""
        # Test with a mock to verify the parameter flow
        with patch('py_spring_model.core.model.PySpringModel.create_session') as mock_create_session:
            mock_session = MagicMock()
            mock_create_session.return_value = mock_session
            
            # Test with should_commit=True
            with PySpringModel.create_managed_session(should_commit=True):
                pass
            mock_session.commit.assert_called_once()
            
            # Reset mock
            mock_session.reset_mock()
            
            # Test with should_commit=False
            with PySpringModel.create_managed_session(should_commit=False):
                pass
            mock_session.commit.assert_not_called() 