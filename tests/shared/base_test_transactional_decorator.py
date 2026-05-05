import pytest
from unittest.mock import patch
from sqlalchemy import text
from sqlmodel import Field, SQLModel

from py_spring_model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, Transactional
from py_spring_model.core.propagation import Propagation, TransactionRequiredError, ExistingTransactionError


class TransactionalTestUser(PySpringModel, table=True):
    """Test model for transactional operations"""
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int = Field(default=0)


class BaseTransactionalDecorator:
    """Test suite for the @Transactional decorator"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up test environment with in-memory SQLite database"""
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([TransactionalTestUser])
        
        # Clear any existing session
        SessionContextHolder.clear()
        
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        """Tear down test environment"""
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)
        PySpringModel._engine = None
        PySpringModel._metadata = None
        PySpringModel._connection = None

    def test_single_transactional_success(self):
        """Test that a single @Transactional function commits successfully"""
        
        @Transactional
        def create_user():
            session = SessionContextHolder.get_or_create_session()
            user = TransactionalTestUser(name="John Doe", email="john@example.com", age=30)
            session.add(user)
            session.flush()  # To get the ID
            return user
        
        # Execute the transactional function
        result = create_user()
        
        # Verify the user was created and committed
        assert result.name == "John Doe"
        assert result.email == "john@example.com"
        assert result.age == 30
        
        # Verify session is cleared after transaction
        assert not SessionContextHolder.has_session()
        
        # Verify data persisted to database
        with PySpringModel.create_managed_session() as session:
            users = session.execute(text("SELECT * FROM transactional_test_user")).fetchall()
            assert len(users) == 1
            assert users[0].name == "John Doe"

    def test_single_transactional_rollback(self):
        """Test that a single @Transactional function rolls back on exception"""
        
        @Transactional
        def create_user_with_error():
            session = SessionContextHolder.get_or_create_session()
            user = TransactionalTestUser(name="Jane Doe", email="jane@example.com", age=25)
            session.add(user)
            session.flush()
            raise ValueError("Simulated error")
        
        # Execute the transactional function and expect exception
        with pytest.raises(ValueError, match="Simulated error"):
            create_user_with_error()
        
        # Verify session is cleared after rollback
        assert not SessionContextHolder.has_session()
        
        # Verify no data persisted to database
        with PySpringModel.create_managed_session() as session:
            users = session.execute(text("SELECT * FROM transactional_test_user")).fetchall()
            assert len(users) == 0

    def test_nested_transactional_success(self):
        """Test that nested @Transactional functions share the same session and commit at top level"""
        
        @Transactional
        def create_user(name: str, email: str):
            session = SessionContextHolder.get_or_create_session()
            user = TransactionalTestUser(name=name, email=email, age=30)
            session.add(user)
            session.flush()
            return user
        
        @Transactional
        def update_user_age(user_id: int, new_age: int):
            session = SessionContextHolder.get_or_create_session()
            session.execute(text(f"UPDATE transactional_test_user SET age = {new_age} WHERE id = {user_id}"))
            
        @Transactional
        def create_and_update_user():
            # This should share the same session with nested calls
            user = create_user("Alice Smith", "alice@example.com")
            update_user_age(user.id, 35)
            return user
        
        # Execute the outer transactional function
        result = create_and_update_user()
        
        # Verify session is cleared after transaction
        assert not SessionContextHolder.has_session()
        
        # Verify both operations were committed
        with PySpringModel.create_managed_session() as session:
            users = session.execute(text("SELECT * FROM transactional_test_user")).fetchall()
            assert len(users) == 1
            assert users[0].name == "Alice Smith"
            assert users[0].age == 35  # Updated by nested function

    def test_nested_transactional_rollback_from_inner(self):
        """Test that exception in nested @Transactional causes rollback at top level"""
        
        @Transactional
        def create_user(name: str, email: str):
            session = SessionContextHolder.get_or_create_session()
            user = TransactionalTestUser(name=name, email=email, age=30)
            session.add(user)
            session.flush()
            return user
        
        @Transactional
        def update_user_with_error(user_id: int):
            session = SessionContextHolder.get_or_create_session()
            session.execute(text(f"UPDATE transactional_test_user SET age = 40 WHERE id = {user_id}"))
            raise RuntimeError("Update failed")
        
        @Transactional
        def create_and_update_user_with_error():
            user = create_user("Bob Johnson", "bob@example.com")
            update_user_with_error(user.id)  # This will raise an exception
            return user
        
        # Execute and expect exception
        with pytest.raises(RuntimeError, match="Update failed"):
            create_and_update_user_with_error()
        
        # Verify session is cleared after rollback
        assert not SessionContextHolder.has_session()
        
        # Verify no data persisted (everything rolled back)
        with PySpringModel.create_managed_session() as session:
            users = session.execute(text("SELECT * FROM transactional_test_user")).fetchall()
            assert len(users) == 0

    def test_nested_transactional_rollback_from_outer(self):
        """Test that exception in outer @Transactional causes rollback after nested calls"""
        
        @Transactional
        def create_user(name: str, email: str):
            session = SessionContextHolder.get_or_create_session()
            user = TransactionalTestUser(name=name, email=email, age=30)
            session.add(user)
            session.flush()
            return user
        
        @Transactional
        def update_user_age(user_id: int, new_age: int):
            session = SessionContextHolder.get_or_create_session()
            session.execute(text(f"UPDATE transactional_test_user SET age = {new_age} WHERE id = {user_id}"))
        
        @Transactional
        def create_update_and_fail():
            user = create_user("Charlie Brown", "charlie@example.com")
            update_user_age(user.id, 45)
            # Both nested operations succeeded, but outer fails
            raise Exception("Outer operation failed")
        
        # Execute and expect exception
        with pytest.raises(Exception, match="Outer operation failed"):
            create_update_and_fail()
        
        # Verify session is cleared after rollback
        assert not SessionContextHolder.has_session()
        
        # Verify no data persisted (everything rolled back)
        with PySpringModel.create_managed_session() as session:
            users = session.execute(text("SELECT * FROM transactional_test_user")).fetchall()
            assert len(users) == 0

    def test_session_sharing_across_nested_transactions(self):
        """Test that nested @Transactional functions share the same session instance"""
        
        captured_sessions = []
        
        @Transactional
        def inner_function():
            session = SessionContextHolder.get_or_create_session()
            captured_sessions.append(session)
            user = TransactionalTestUser(name="Inner User", email="inner@example.com", age=25)
            session.add(user)
            session.flush()
            return session
        
        @Transactional
        def middle_function():
            session = SessionContextHolder.get_or_create_session()
            captured_sessions.append(session)
            inner_session = inner_function()
            return session, inner_session
        
        @Transactional
        def outer_function():
            session = SessionContextHolder.get_or_create_session()
            captured_sessions.append(session)
            middle_session, inner_session = middle_function()
            return session, middle_session, inner_session
        
        # Execute nested transactions
        outer_session, middle_session, inner_session = outer_function()
        
        # Verify all functions used the same session instance
        assert len(captured_sessions) == 3
        assert captured_sessions[0] is captured_sessions[1]  # outer and middle
        assert captured_sessions[1] is captured_sessions[2]  # middle and inner
        assert outer_session is middle_session is inner_session
        
        # Verify session is cleared after transaction
        assert not SessionContextHolder.has_session()

    def test_transactional_session_context_isolation(self):
        """Test that @Transactional properly isolates session context"""
        
        @Transactional
        def first_transaction():
            session = SessionContextHolder.get_or_create_session()
            user1 = TransactionalTestUser(name="User 1", email="user1@example.com", age=30)
            session.add(user1)
            session.flush()
            return user1.id
        
        @Transactional
        def second_transaction():
            session = SessionContextHolder.get_or_create_session()
            user2 = TransactionalTestUser(name="User 2", email="user2@example.com", age=35)
            session.add(user2)
            session.flush()
            return user2.id
        
        # Execute separate transactions
        first_transaction()
        second_transaction()
        
        # Verify sessions were properly isolated
        assert not SessionContextHolder.has_session()
        
        # Verify both transactions committed separately
        with PySpringModel.create_managed_session() as session:
            users = session.execute(text("SELECT * FROM transactional_test_user ORDER BY id")).fetchall()
            assert len(users) == 2
            assert users[0].name == "User 1"
            assert users[1].name == "User 2"

    def test_transactional_preserves_function_metadata(self):
        """Test that @Transactional preserves original function metadata"""
        
        @Transactional
        def documented_function(param1: str, param2: int = 10) -> str:
            """This is a documented function with parameters."""
            return f"{param1}_{param2}"
        
        # Verify function metadata is preserved
        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ is not None and "documented function" in documented_function.__doc__
        
        # Verify function still works correctly
        result = documented_function("test", 20)
        assert result == "test_20"

    def test_transactional_commit_rollback_behavior(self):
        """Test the core commit/rollback behavior of nested transactions"""
        
        commit_calls = []
        rollback_calls = []
        
        # Mock session to track commit/rollback calls
        original_session_class = PySpringModel.create_session
        
        def mock_create_session():
            session = original_session_class()
            original_commit = session.commit
            original_rollback = session.rollback
            
            def mock_commit():
                commit_calls.append("commit")
                return original_commit()
            
            def mock_rollback():
                rollback_calls.append("rollback")
                return original_rollback()
            
            session.commit = mock_commit
            session.rollback = mock_rollback
            return session
        
        @Transactional 
        def inner_operation():
            session = SessionContextHolder.get_or_create_session()
            user = TransactionalTestUser(name="Test", email="test@example.com", age=30)
            session.add(user)
            session.flush()
        
        @Transactional
        def outer_operation():
            inner_operation()
        
        # Test successful nested transaction
        with patch.object(PySpringModel, 'create_session', side_effect=mock_create_session):
            outer_operation()
        
        # Only the outermost transaction should commit
        assert len(commit_calls) == 1
        assert len(rollback_calls) == 0
        
        # Reset counters
        commit_calls.clear()
        rollback_calls.clear()
        
        @Transactional
        def inner_operation_with_error():
            session = SessionContextHolder.get_or_create_session()
            user = TransactionalTestUser(name="Test2", email="test2@example.com", age=25)
            session.add(user)
            session.flush()
            raise ValueError("Inner error")
        
        @Transactional
        def outer_operation_with_error():
            inner_operation_with_error()
        
        # Test failed nested transaction
        with patch.object(PySpringModel, 'create_session', side_effect=mock_create_session):
            with pytest.raises(ValueError):
                outer_operation_with_error()
        
        # Only the outermost transaction should rollback
        assert len(commit_calls) == 0
        assert len(rollback_calls) == 1

    def test_bare_transactional_still_works(self):
        """@Transactional without arguments still works as REQUIRED."""
        @Transactional
        def simple_op():
            session = SessionContextHolder.get_or_create_session()
            user = TransactionalTestUser(name="Bare", email="bare@test.com", age=1)
            session.add(user)
            session.flush()
            return user

        result = simple_op()
        assert result.name == "Bare"
        assert not SessionContextHolder.has_session()

    def test_parameterized_required(self):
        """@Transactional(propagation=Propagation.REQUIRED) works."""
        @Transactional(propagation=Propagation.REQUIRED)
        def create():
            session = SessionContextHolder.get_or_create_session()
            user = TransactionalTestUser(name="ParamReq", email="pr@test.com", age=2)
            session.add(user)
            session.flush()
            return user

        result = create()
        assert result.name == "ParamReq"

        with PySpringModel.create_managed_session() as session:
            users = session.execute(text("SELECT * FROM transactional_test_user WHERE name='ParamReq'")).fetchall()
            assert len(users) == 1

    def test_parameterized_requires_new(self):
        """@Transactional(propagation=Propagation.REQUIRES_NEW) creates independent session."""
        captured_sessions = []

        @Transactional
        def outer():
            outer_session = SessionContextHolder.get_or_create_session()
            captured_sessions.append(("outer", outer_session))
            inner()

        @Transactional(propagation=Propagation.REQUIRES_NEW)
        def inner():
            inner_session = SessionContextHolder.get_or_create_session()
            captured_sessions.append(("inner", inner_session))

        outer()

        # REQUIRES_NEW must create a different session from the outer
        assert len(captured_sessions) == 2
        assert captured_sessions[0][0] == "outer"
        assert captured_sessions[1][0] == "inner"
        assert captured_sessions[0][1] is not captured_sessions[1][1]
        assert not SessionContextHolder.has_session()

    def test_parameterized_mandatory_raises(self):
        """@Transactional(propagation=Propagation.MANDATORY) raises without existing txn."""
        @Transactional(propagation=Propagation.MANDATORY)
        def needs_txn():
            return "should not reach"

        with pytest.raises(TransactionRequiredError):
            needs_txn()

    def test_parameterized_never_raises_with_txn(self):
        """@Transactional(propagation=Propagation.NEVER) raises when txn exists."""
        @Transactional(propagation=Propagation.NEVER)
        def no_txn_allowed():
            return "ok without txn"

        # Works without transaction
        assert no_txn_allowed() == "ok without txn"

        # Fails with transaction
        @Transactional
        def outer():
            @Transactional(propagation=Propagation.NEVER)
            def inner():
                return "should not reach"
            return inner()

        with pytest.raises(ExistingTransactionError):
            outer()

    def test_parameterized_preserves_function_metadata(self):
        """Parameterized @Transactional preserves function name and docstring."""
        @Transactional(propagation=Propagation.SUPPORTS)
        def documented(x: int) -> str:
            """A documented function."""
            return str(x)

        assert documented.__name__ == "documented"
        assert "documented function" in documented.__doc__
        assert documented(42) == "42"