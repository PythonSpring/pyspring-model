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
    
    @Query("UPDATE testuser SET name = {name}, age = {age} WHERE email = {email} RETURNING *", is_modifying=True)
    def update_user_with_commit(self, name: str, email: str, age: int) -> TestUser:
        """UPDATE operation that should commit changes"""
        ...
    
    @Query("UPDATE testuser SET name = {name}, age = {age} WHERE email = {email}", is_modifying=False)
    def update_user_without_commit(self, name: str, email: str, age: int) -> None:
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
    
    @Query("DELETE FROM testuser WHERE email = {email}", is_modifying=True)
    def delete_user_with_commit(self, email: str) -> None:
        """DELETE operation that should commit changes"""
        ...
    
    @Query("DELETE FROM testuser WHERE email = {email}", is_modifying=False)
    def delete_user_without_commit(self, email: str) -> None:
        """DELETE operation that should NOT commit changes"""
        ...
    
    @Query("UPDATE testuser SET age = age + {increment} WHERE age > {min_age}", is_modifying=True)
    def bulk_update_ages_with_commit(self, increment: int, min_age: int) -> None:
        """Bulk UPDATE operation that should commit changes"""
        ...
    
    @Query("SELECT * FROM testuser WHERE age > {min_age} ORDER BY age DESC")
    def find_users_by_min_age(self, min_age: int) -> List[TestUser]:
        """SELECT with parameters (readonly)"""
        ...
    
    @Query("SELECT COUNT(*) as count FROM testuser WHERE age BETWEEN {min_age} AND {max_age}")
    def count_users_by_age_range(self, min_age: int, max_age: int) -> int:
        """Aggregate query (readonly)"""
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
    
    # =====================================================
    # REAL DATABASE INTEGRATION TESTS
    # =====================================================
    
    def test_real_database_insert_without_commit_rollback(self):
        """Integration test: INSERT without commit should not persist after rollback"""
        initial_count = len(self.repository.find_all())
        
        # Attempt to insert without commit in a session that gets rolled back
        try:
            with PySpringModel.create_managed_session(should_commit=False) as session:
                # This should not commit
                result = session.execute(text(
                    "INSERT INTO testuser (name, email, age) VALUES ('Temp User', 'temp@example.com', 99)"
                ))
                # Verify the user exists within this session
                temp_result = session.execute(text(
                    "SELECT * FROM testuser WHERE email = 'temp@example.com'"
                )).first()
                assert temp_result is not None
                # Force rollback by raising exception
                raise Exception("Intentional rollback")
        except Exception:
            pass  # Expected rollback
        
        # Verify the user does not exist after rollback
        final_count = len(self.repository.find_all())
        assert final_count == initial_count
        
        # Double-check by direct query
        with PySpringModel.create_managed_session() as session:
            result = session.execute(text(
                "SELECT * FROM testuser WHERE email = 'temp@example.com'"
            )).first()
            assert result is None
    
    def test_real_database_update_operations_with_persistence(self):
        """Integration test: UPDATE operations with real persistence verification"""
        # Create initial user
        test_user = TestUser(name="Update Test User", email="update@example.com", age=25)
        saved_user = self.repository.save(test_user)
        original_age = saved_user.age
        
        # Update using commit=True
        with PySpringModel.create_managed_session(should_commit=True) as session:
            session.execute(text(
                f"UPDATE testuser SET age = {original_age + 10} WHERE email = 'update@example.com'"
            ))
        
                          # Verify the change persisted
        with PySpringModel.create_managed_session() as session:
             result = session.execute(text(
                 "SELECT age FROM testuser WHERE email = 'update@example.com'"
             )).first()
             assert result is not None
             assert result.age == original_age + 10
         
         # Update using commit=False and verify it doesn't persist after session close
        try:
             with PySpringModel.create_managed_session(should_commit=False) as session:
                 session.execute(text(
                     f"UPDATE testuser SET age = {original_age + 20} WHERE email = 'update@example.com'"
                 ))
                 # Verify change within session
                 temp_result = session.execute(text(
                     "SELECT age FROM testuser WHERE email = 'update@example.com'"
                 )).first()
                 assert temp_result is not None
                 assert temp_result.age == original_age + 20
                 # Force rollback
                 raise Exception("Intentional rollback")
        except Exception:
             pass
         
         # Verify the uncommitted change was rolled back
        with PySpringModel.create_managed_session() as session:
             result = session.execute(text(
                 "SELECT age FROM testuser WHERE email = 'update@example.com'"
             )).first()
             assert result is not None
             assert result.age == original_age + 10  # Should still be the committed value
    
    def test_real_database_delete_operations_with_persistence(self):
        """Integration test: DELETE operations with real persistence verification"""
        # Create test user for deletion
        test_user = TestUser(name="Delete Test User", email="delete@example.com", age=30)
        self.repository.save(test_user)
        
        # Verify user exists
        users_before = self.repository.find_all()
        delete_user = next((u for u in users_before if u.email == "delete@example.com"), None)
        assert delete_user is not None
        
        # Delete with commit=False (should not persist)
        try:
            with PySpringModel.create_managed_session(should_commit=False) as session:
                session.execute(text("DELETE FROM testuser WHERE email = 'delete@example.com'"))
                # Verify deletion within session
                temp_result = session.execute(text(
                    "SELECT * FROM testuser WHERE email = 'delete@example.com'"
                )).first()
                assert temp_result is None
                # Force rollback
                raise Exception("Intentional rollback")
        except Exception:
            pass
        
        # Verify user still exists after rollback
        with PySpringModel.create_managed_session() as session:
            result = session.execute(text(
                "SELECT * FROM testuser WHERE email = 'delete@example.com'"
            )).first()
            assert result is not None
        
        # Delete with commit=True (should persist)
        with PySpringModel.create_managed_session(should_commit=True) as session:
            session.execute(text("DELETE FROM testuser WHERE email = 'delete@example.com'"))
        
        # Verify user is gone
        with PySpringModel.create_managed_session() as session:
            result = session.execute(text(
                "SELECT * FROM testuser WHERE email = 'delete@example.com'"
            )).first()
            assert result is None
    
    def test_real_database_bulk_operations_performance(self):
        """Integration test: Bulk operations with commit control for performance"""
        # Create multiple users for bulk operations
        bulk_users = []
        for i in range(5):
            user = TestUser(name=f"Bulk User {i}", email=f"bulk{i}@example.com", age=20 + i)
            bulk_users.append(user)
            self.repository.save(user)
        
        initial_count = len(self.repository.find_all())
        
        # Bulk update with commit=True
        with PySpringModel.create_managed_session(should_commit=True) as session:
            session.execute(text("UPDATE testuser SET age = age + 5 WHERE email LIKE 'bulk%@example.com'"))
        
        # Verify all bulk users were updated
        with PySpringModel.create_managed_session() as session:
            results = session.execute(text(
                "SELECT name, age FROM testuser WHERE email LIKE 'bulk%@example.com' ORDER BY name"
            )).fetchall()
            for i, result in enumerate(results):
                expected_age = 20 + i + 5  # Original age + increment
                assert result.age == expected_age
    
    def test_real_database_complex_query_operations(self):
        """Integration test: Complex queries with joins and aggregations"""
        # Create test data with different age ranges
        test_users = [
            TestUser(name="Young User 1", email="young1@example.com", age=18),
            TestUser(name="Young User 2", email="young2@example.com", age=20),
            TestUser(name="Adult User 1", email="adult1@example.com", age=35),
            TestUser(name="Adult User 2", email="adult2@example.com", age=40),
            TestUser(name="Senior User", email="senior@example.com", age=65),
        ]
        
        for user in test_users:
            self.repository.save(user)
        
        # Test complex SELECT with aggregation (readonly, no commit)
        with PySpringModel.create_managed_session(should_commit=False) as session:
            # Count users by age range
            young_count = session.execute(text(
                "SELECT COUNT(*) as count FROM testuser WHERE age < 25"
            )).first()
            assert young_count is not None
            assert young_count.count is not None
            young_count = young_count.count
            
            adult_count = session.execute(text(
                "SELECT COUNT(*) as count FROM testuser WHERE age BETWEEN 25 AND 60"
            )).first()
            assert adult_count is not None
            assert adult_count.count is not None
            adult_count = adult_count.count
            
            senior_count = session.execute(text(
                "SELECT COUNT(*) as count FROM testuser WHERE age > 60"
            )).first()
            assert senior_count is not None
            assert senior_count.count is not None
            senior_count = senior_count.count
            
            assert young_count >= 2  # Young users + potentially others
            assert adult_count >= 2  # Adult users + potentially others  
            assert senior_count >= 1  # Senior user + potentially others
        
        # Test conditional UPDATE with complex WHERE clause
        with PySpringModel.create_managed_session(should_commit=True) as session:
            # Update all users over 30 to have age + 1
            session.execute(text(
                "UPDATE testuser SET age = age + 1 WHERE age > 30 AND email LIKE '%@example.com'"
            ))
        
        # Verify the conditional update
        with PySpringModel.create_managed_session() as session:
            adult1_result = session.execute(text(
                "SELECT age FROM testuser WHERE email = 'adult1@example.com'"
            )).first()
            adult2_result = session.execute(text(
                "SELECT age FROM testuser WHERE email = 'adult2@example.com'"
            )).first()
            senior_result = session.execute(text(
                "SELECT age FROM testuser WHERE email = 'senior@example.com'"
            )).first()
            young1_result = session.execute(text(
                "SELECT age FROM testuser WHERE email = 'young1@example.com'"
            )).first()
            assert adult1_result is not None
            assert adult1_result.age is not None
            assert adult2_result is not None
            assert adult2_result.age is not None
            assert senior_result is not None
            assert senior_result.age is not None
            assert young1_result is not None
            assert young1_result.age is not None
            # Adults and seniors should be incremented
            assert adult1_result.age == 36  # 35 + 1
            assert adult2_result.age == 41  # 40 + 1
            assert senior_result.age == 66  # 65 + 1
            # Young users should be unchanged
            assert young1_result.age == 18  # Unchanged
    
    def test_real_database_transaction_isolation_levels(self):
        """Integration test: Transaction behavior with different commit strategies"""
        # Create base user
        base_user = TestUser(name="Isolation Test", email="isolation@example.com", age=50)
        self.repository.save(base_user)
        
        # Test concurrent access simulation
        # Session 1: Read-only access (no commit needed)
        with PySpringModel.create_managed_session(should_commit=False) as session1:
            original_data = session1.execute(text(
                "SELECT name, age FROM testuser WHERE email = 'isolation@example.com'"
            )).first()
            assert original_data is not None
            
            # Session 2: Modify with commit
            with PySpringModel.create_managed_session(should_commit=True) as session2:
                session2.execute(text(
                    "UPDATE testuser SET age = 999 WHERE email = 'isolation@example.com'"
                ))
            
            # Session 1 should still see original data (isolation)
            current_data = session1.execute(text(
                "SELECT name, age FROM testuser WHERE email = 'isolation@example.com'"
            )).first()
            # Note: In SQLite with default isolation, this might see the change
            # This test documents the behavior rather than asserting specific isolation
            assert current_data is not None
            logger.info(f"Original age: {original_data.age}, Current age in session1: {current_data.age}")
        
        # Verify the change persisted
        with PySpringModel.create_managed_session() as session:
            result = session.execute(text(
                "SELECT age FROM testuser WHERE email = 'isolation@example.com'"
            )).first()
            assert result is not None
            assert result.age is not None
            assert result.age == 999
    
    def test_real_database_error_handling_with_constraints(self):
        """Integration test: Error handling with database constraints and rollback"""
        # Create user with unique email
        unique_user = TestUser(name="Unique User", email="unique@example.com", age=25)
        self.repository.save(unique_user)
        
        # Attempt to insert duplicate email without commit (should fail but not affect DB)
        initial_count = len(self.repository.find_all())
        
        try:
            with PySpringModel.create_managed_session(should_commit=False) as session:
                # This should fail due to unique constraint (if enforced)
                session.execute(text(
                    "INSERT INTO testuser (name, email, age) VALUES ('Duplicate User', 'unique@example.com', 30)"
                ))
                # If it somehow succeeds, force rollback
                raise Exception("Force rollback")
        except Exception as e:
            logger.info(f"Expected constraint violation or forced rollback: {e}")
        
        # Verify no extra records were added
        final_count = len(self.repository.find_all())
        assert final_count == initial_count
        
        # Verify original user is unchanged
        with PySpringModel.create_managed_session() as session:
            result = session.execute(text(
                "SELECT name, age FROM testuser WHERE email = 'unique@example.com'"
            )).first()
            assert result is not None
            assert result.name is not None
            assert result.age is not None
            assert result.name == "Unique User"
            assert result.age == 25
    
    def test_real_database_batch_insert_with_commit_control(self):
        """Integration test: Batch operations with controlled commits"""
        initial_count = len(self.repository.find_all())
        
        # Batch insert with commit=True
        batch_data = [
            ("Batch User 1", "batch1@example.com", 21),
            ("Batch User 2", "batch2@example.com", 22),
            ("Batch User 3", "batch3@example.com", 23),
        ]
        
        with PySpringModel.create_managed_session(should_commit=True) as session:
            for name, email, age in batch_data:
                session.execute(text(
                    f"INSERT INTO testuser (name, email, age) VALUES ('{name}', '{email}', {age})"
                ))
        
        # Verify all batch inserts persisted
        final_count = len(self.repository.find_all())
        assert final_count == initial_count + len(batch_data)
        
        # Verify specific batch users exist
        with PySpringModel.create_managed_session() as session:
            for name, email, age in batch_data:
                result = session.execute(text(
                    f"SELECT name, age FROM testuser WHERE email = '{email}'"
                )).first()
                assert result is not None
                assert result.name == name
                assert result.age == age
        
        # Test batch insert with commit=False (should not persist)
        rollback_data = [
            ("Rollback User 1", "rollback1@example.com", 31),
            ("Rollback User 2", "rollback2@example.com", 32),
        ]
        
        try:
            with PySpringModel.create_managed_session(should_commit=False) as session:
                for name, email, age in rollback_data:
                    session.execute(text(
                        f"INSERT INTO testuser (name, email, age) VALUES ('{name}', '{email}', {age})"
                    ))
                # Force rollback
                raise Exception("Intentional rollback")
        except Exception:
            pass
        
        # Verify rollback users do not exist
        rollback_final_count = len(self.repository.find_all())
        assert rollback_final_count == final_count  # Should be same as before rollback attempt
        
        with PySpringModel.create_managed_session() as session:
            for name, email, age in rollback_data:
                result = session.execute(text(
                    f"SELECT * FROM testuser WHERE email = '{email}'"
                )).first()
                assert result is None 