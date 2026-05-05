"""
Tests for PySpringSession custom session behavior.
Covers: add(), add_all(), refresh_current_session_instances(), commit() override.
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import text
from sqlmodel import Field, SQLModel

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.py_spring_session import PySpringSession
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class SessionUser(PySpringModel, table=True):
    __tablename__ = "session_user"
    id: int = Field(default=None, primary_key=True)
    name: str


class BasePySpringSessionAdd:
    """Tests for add() and add_all() overrides that track current_session_instance."""

    @pytest.fixture(autouse=True)
    def setup(self):
        PySpringModel.set_engine(self.engine)
        SQLModel.metadata.create_all(self.engine)
        SessionContextHolder.clear()
        yield
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)
        PySpringModel._engine = None

    def test_add_tracks_instance(self):
        session = PySpringSession(self.engine, expire_on_commit=False)
        user = SessionUser(name="Alice")
        session.add(user)
        assert user in session.current_session_instance

    def test_add_multiple_instances_tracked(self):
        session = PySpringSession(self.engine, expire_on_commit=False)
        u1 = SessionUser(name="Alice")
        u2 = SessionUser(name="Bob")
        session.add(u1)
        session.add(u2)
        assert len(session.current_session_instance) == 2
        assert u1 in session.current_session_instance
        assert u2 in session.current_session_instance

    def test_add_all_tracks_instances(self):
        """add_all extends the tracking list. Since super().add_all() internally
        calls add() for each instance, each item appears twice (once from extend,
        once from add). This test documents the actual behavior."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        users = [SessionUser(name="Alice"), SessionUser(name="Bob"), SessionUser(name="Charlie")]
        session.add_all(users)
        # Each user appears twice: once via extend(), once via super().add_all() -> add()
        assert len(session.current_session_instance) == 6
        for user in users:
            assert user in session.current_session_instance

    def test_add_delegates_to_super(self):
        """add() should actually add the instance to the SQLAlchemy session."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        user = SessionUser(name="Alice")
        session.add(user)
        session.commit()
        result = session.execute(text("SELECT name FROM session_user")).fetchall()
        assert len(result) == 1
        assert result[0].name == "Alice"
        session.close()

    def test_add_all_delegates_to_super(self):
        """add_all() should actually add all instances to the SQLAlchemy session."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        users = [SessionUser(name="A"), SessionUser(name="B")]
        session.add_all(users)
        session.commit()
        result = session.execute(text("SELECT name FROM session_user ORDER BY name")).fetchall()
        assert len(result) == 2
        assert result[0].name == "A"
        assert result[1].name == "B"
        session.close()

    def test_current_session_instance_starts_empty(self):
        session = PySpringSession(self.engine, expire_on_commit=False)
        assert session.current_session_instance == []
        session.close()


class BasePySpringSessionRefresh:
    """Tests for refresh_current_session_instances()."""

    @pytest.fixture(autouse=True)
    def setup(self):
        PySpringModel.set_engine(self.engine)
        SQLModel.metadata.create_all(self.engine)
        SessionContextHolder.clear()
        yield
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)
        PySpringModel._engine = None

    def test_refresh_persistent_instance(self):
        """Refreshing a committed (persistent) instance should succeed."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        user = SessionUser(name="Alice")
        session.add(user)
        session.flush()  # Make persistent
        # Modify in DB directly
        session.execute(text("UPDATE session_user SET name = 'Updated' WHERE id = :id"), {"id": user.id})
        session.refresh_current_session_instances()
        assert user.name == "Updated"
        session.rollback()
        session.close()

    def test_refresh_skips_non_persistent_instance(self):
        """Non-persistent (transient) instances should be skipped without error."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        user = SessionUser(name="Transient")
        # Manually add to tracking without adding to session
        session.current_session_instance.append(user)
        # Should not raise
        session.refresh_current_session_instances()
        session.close()

    def test_refresh_handles_exception_gracefully(self):
        """If refresh fails for an instance, it should be skipped (logged, not raised)."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        user = SessionUser(name="Alice")
        session.add(user)
        session.flush()

        # Expire the instance then close the underlying connection to cause refresh failure
        # Instead, mock the refresh to raise
        original_refresh = session.refresh

        call_count = 0
        def failing_refresh(instance):
            nonlocal call_count
            call_count += 1
            raise Exception("Simulated refresh failure")

        session.refresh = failing_refresh
        # Should not raise despite the refresh failure
        session.refresh_current_session_instances()
        assert call_count == 1

        session.refresh = original_refresh
        session.rollback()
        session.close()

    def test_refresh_empty_instance_list(self):
        """Refreshing with no tracked instances should be a no-op."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        assert session.current_session_instance == []
        session.refresh_current_session_instances()  # Should not raise
        session.close()


class BasePySpringSessionCommit:
    """Tests for commit() override that suppresses nested commits."""

    @pytest.fixture(autouse=True)
    def setup(self):
        PySpringModel.set_engine(self.engine)
        SQLModel.metadata.create_all(self.engine)
        SessionContextHolder.clear()
        yield
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)
        PySpringModel._engine = None

    def test_commit_suppressed_when_depth_greater_than_one(self):
        """When depth > 1 (nested transaction), commit should be suppressed."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        state = TransactionState(session=session, depth=2)
        SessionContextHolder.push_state(state)

        user = SessionUser(name="Nested")
        session.add(user)

        # commit() should be suppressed — the data should NOT be committed
        session.commit()

        # Verify super().commit() was NOT called by checking if the data is still pending
        # We can check this by rolling back and seeing that the user disappears
        session.rollback()
        result = session.execute(text("SELECT COUNT(*) FROM session_user")).scalar()
        assert result == 0

        SessionContextHolder.pop_state()
        session.close()

    def test_commit_proceeds_when_depth_is_one(self):
        """When depth == 1 (outermost transaction), commit should proceed normally."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        state = TransactionState(session=session, depth=1)
        SessionContextHolder.push_state(state)

        user = SessionUser(name="Outermost")
        session.add(user)
        session.commit()

        # Verify data was committed
        result = session.execute(text("SELECT name FROM session_user")).fetchall()
        assert len(result) == 1
        assert result[0].name == "Outermost"

        SessionContextHolder.pop_state()
        session.close()

    def test_commit_proceeds_when_no_state(self):
        """When no TransactionState exists, commit should proceed normally."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        user = SessionUser(name="NoState")
        session.add(user)
        session.commit()

        result = session.execute(text("SELECT name FROM session_user")).fetchall()
        assert len(result) == 1
        assert result[0].name == "NoState"
        session.close()

    def test_commit_calls_refresh_after_real_commit(self):
        """After a real commit (depth <= 1), refresh_current_session_instances should be called."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        user = SessionUser(name="Refreshed")
        session.add(user)

        with patch.object(session, "refresh_current_session_instances") as mock_refresh:
            session.commit()
            mock_refresh.assert_called_once()

        session.close()

    def test_commit_does_not_refresh_when_suppressed(self):
        """When commit is suppressed (depth > 1), refresh should NOT be called."""
        session = PySpringSession(self.engine, expire_on_commit=False)
        state = TransactionState(session=session, depth=2)
        SessionContextHolder.push_state(state)

        user = SessionUser(name="NoRefresh")
        session.add(user)

        with patch.object(session, "refresh_current_session_instances") as mock_refresh:
            session.commit()
            mock_refresh.assert_not_called()

        SessionContextHolder.pop_state()
        session.rollback()
        session.close()
